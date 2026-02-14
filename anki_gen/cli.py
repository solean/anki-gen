from __future__ import annotations

import argparse
import os
import sys
from typing import List

from .align import align_by_overlap
from .dotenv import load_dotenv
from .export import export_apkg, export_csv
from .llm import LlmConfig, LlmError, LlmItem, select_candidates
from .media import ensure_dir, extract_audio, extract_image, MediaError
from .models import CardLine, SubtitleLine
from .review import ReviewRow, load_review_tsv, write_review_tsv
from .srt import load_srt, merge_adjacent, MissingDependencyError as SrtDependencyError
from .text import (
    MissingDependencyError as TextDependencyError,
    is_sfx_only,
    normalize_text,
    romaji_text,
)


def _prepare_lines(lines: List[SubtitleLine], gap_ms: int, drop_sfx: bool) -> List[SubtitleLine]:
    prepared: List[SubtitleLine] = []
    for line in lines:
        if drop_sfx and is_sfx_only(line.text):
            continue
        text = normalize_text(line.text)
        if not text:
            continue
        prepared.append(SubtitleLine(start_ms=line.start_ms, end_ms=line.end_ms, text=text))
    return merge_adjacent(prepared, gap_ms=gap_ms)


def _default_api_base(provider: str) -> str:
    if provider == "openrouter":
        return "https://openrouter.ai/api/v1"
    if provider == "anthropic":
        return "https://api.anthropic.com/v1"
    return "https://api.openai.com/v1"


def _default_endpoint(provider: str) -> str:
    if provider == "anthropic":
        return "/messages"
    return "/chat/completions"


def _resolve_api_key(provider: str, cli_value: str) -> str:
    if cli_value:
        return cli_value
    if provider == "openrouter":
        return os.environ.get("OPENROUTER_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY", "")
    return os.environ.get("OPENAI_API_KEY", "")


def _resolve_api_base(provider: str, cli_value: str) -> str:
    if cli_value:
        return cli_value
    if provider == "openrouter":
        return os.environ.get("OPENROUTER_API_BASE", "") or _default_api_base(provider)
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_BASE", "") or _default_api_base(provider)
    return os.environ.get("OPENAI_API_BASE", "") or _default_api_base(provider)


def _resolve_endpoint(provider: str, cli_value: str) -> str:
    if cli_value:
        return cli_value
    if provider == "openrouter":
        return os.environ.get("OPENROUTER_API_ENDPOINT", "") or _default_endpoint(provider)
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_ENDPOINT", "") or _default_endpoint(provider)
    return os.environ.get("OPENAI_API_ENDPOINT", "") or _default_endpoint(provider)


def build_arg_parser() -> argparse.ArgumentParser:
    # Load .env first so CLI defaults can read OPENAI_* values from it.
    load_dotenv()

    parser = argparse.ArgumentParser(description="Generate Anki cards from video + JP/EN subtitles")
    parser.add_argument("--video", required=True, help="Path to the video file")
    parser.add_argument("--jp-srt", help="Path to Japanese .srt")
    parser.add_argument("--en-srt", help="Path to English .srt")
    parser.add_argument("--out-dir", default="output", help="Output directory")
    parser.add_argument("--format", choices=["csv", "apkg"], default="csv")
    parser.add_argument("--deck-name", default="AnkiGen Deck", help="Deck name for apkg export")
    parser.add_argument("--audio-track", type=int, default=0, help="Audio track index for ffmpeg")
    parser.add_argument("--video-track", type=int, default=0, help="Video track index for ffmpeg")
    parser.add_argument("--gap-merge-ms", type=int, default=400, help="Merge lines with small gaps")
    parser.add_argument("--pad-before-ms", type=int, default=100, help="Audio padding before line")
    parser.add_argument("--pad-after-ms", type=int, default=200, help="Audio padding after line")
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N lines")
    parser.add_argument(
        "--keep-sfx",
        action="store_true",
        help="Keep SFX-only subtitle lines instead of dropping them",
    )
    parser.add_argument(
        "--review-out",
        help="Write LLM review TSV to this path and exit (no media extraction)",
    )
    parser.add_argument(
        "--review-in",
        help="Generate cards using approved rows from a review TSV",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["openai", "openrouter", "anthropic"],
        default=os.environ.get("LLM_PROVIDER", "openai"),
        help="LLM API provider",
    )
    parser.add_argument(
        "--llm-model",
        default=os.environ.get("LLM_MODEL", os.environ.get("OPENAI_MODEL", "gpt-5-mini")),
        help="LLM model name (or set LLM_MODEL / OPENAI_MODEL)",
    )
    parser.add_argument(
        "--user-level",
        choices=["beginner", "middle", "intermediate", "advanced"],
        default="intermediate",
        help="Learner proficiency for selecting appropriate vocab/grammar",
    )
    parser.add_argument(
        "--llm-api-key",
        default=os.environ.get("LLM_API_KEY", ""),
        help="API key for selected provider (or set LLM_API_KEY)",
    )
    parser.add_argument(
        "--llm-api-base",
        default=os.environ.get("LLM_API_BASE", ""),
        help="Base URL for the LLM API (provider-specific default when omitted)",
    )
    parser.add_argument(
        "--llm-endpoint",
        default=os.environ.get("LLM_API_ENDPOINT", ""),
        help="API endpoint path or full URL (provider-specific default when omitted)",
    )
    parser.add_argument(
        "--llm-temperature",
        type=float,
        default=float(os.environ.get("LLM_TEMPERATURE", os.environ.get("OPENAI_TEMPERATURE", "1.0"))),
        help="Sampling temperature (some models only allow the default value)",
    )
    parser.add_argument(
        "--llm-reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        default=os.environ.get("LLM_REASONING_EFFORT", os.environ.get("OPENAI_REASONING_EFFORT", "minimal")),
        help="Reasoning effort for capable models (default: minimal)",
    )
    parser.add_argument("--llm-batch-size", type=int, default=30)
    parser.add_argument("--llm-timeout", type=int, default=60)
    parser.add_argument(
        "--llm-app-name",
        default=os.environ.get("LLM_APP_NAME", os.environ.get("OPENROUTER_APP_NAME", "")),
        help="Optional app name sent to OpenRouter",
    )
    parser.add_argument(
        "--llm-site-url",
        default=os.environ.get(
            "LLM_SITE_URL",
            os.environ.get("OPENROUTER_SITE_URL", os.environ.get("OPENROUTER_HTTP_REFERER", "")),
        ),
        help="Optional site URL sent to OpenRouter as HTTP-Referer",
    )
    parser.add_argument(
        "--llm-anthropic-version",
        default=os.environ.get("LLM_ANTHROPIC_VERSION", os.environ.get("ANTHROPIC_VERSION", "2023-06-01")),
        help="Anthropic API version header",
    )
    parser.add_argument(
        "--llm-debug",
        action="store_true",
        help="Enable verbose LLM request/response logging to stderr",
    )
    parser.add_argument(
        "--llm-debug-file",
        default=os.environ.get("LLM_DEBUG_FILE", os.environ.get("OPENAI_DEBUG_FILE", "")),
        help="Append verbose LLM logs to this file (or set LLM_DEBUG_FILE)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip media extraction")
    return parser


def main(argv: List[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.review_out and args.review_in:
        print("Cannot use --review-out and --review-in together", file=sys.stderr)
        return 2

    if args.review_in:
        try:
            review_rows = load_review_tsv(args.review_in)
        except FileNotFoundError:
            print(f"Review file not found: {args.review_in}", file=sys.stderr)
            return 1

        approved_rows = [row for row in review_rows if row.approved]
        if not approved_rows:
            print("No approved rows found in review file.", file=sys.stderr)
            return 1

        out_dir = os.path.abspath(args.out_dir)
        audio_dir = os.path.join(out_dir, "media", "audio")
        image_dir = os.path.join(out_dir, "media", "img")
        ensure_dir(audio_dir)
        ensure_dir(image_dir)

        cards: List[CardLine] = []
        for row in approved_rows:
            card_jp = row.focus.strip() if row.focus.strip() else row.jp
            card_en = row.gloss.strip() if row.gloss.strip() else (row.reason.strip() if row.reason.strip() else row.en)
            try:
                romaji = romaji_text(card_jp)
            except TextDependencyError as exc:
                print(str(exc), file=sys.stderr)
                return 1

            audio_file = f"audio_{row.line_id:05d}.mp3"
            image_file = f"img_{row.line_id:05d}.jpg"
            cards.append(
                CardLine(
                    line_id=row.line_id,
                    start_ms=row.start_ms,
                    end_ms=row.end_ms,
                    jp=card_jp,
                    en=card_en,
                    romaji=romaji,
                    audio_file=audio_file,
                    image_file=image_file,
                    source=os.path.basename(args.video),
                )
            )

            if not args.dry_run:
                try:
                    extract_audio(
                        args.video,
                        row.start_ms,
                        row.end_ms,
                        os.path.join(audio_dir, audio_file),
                        audio_track=args.audio_track,
                        pad_before_ms=args.pad_before_ms,
                        pad_after_ms=args.pad_after_ms,
                    )
                    mid_ms = int((row.start_ms + row.end_ms) / 2)
                    extract_image(
                        args.video,
                        mid_ms,
                        os.path.join(image_dir, image_file),
                        video_track=args.video_track,
                    )
                except MediaError as exc:
                    print(f"Media extraction failed at line {row.line_id}: {exc}", file=sys.stderr)
                    return 1

        if args.format == "csv":
            out_path = export_csv(cards, out_dir)
        else:
            out_path = export_apkg(cards, out_dir, deck_name=args.deck_name)

        print(f"Wrote {len(cards)} cards to {out_path}")
        return 0

    if not args.jp_srt or not args.en_srt:
        print("Both --jp-srt and --en-srt are required unless --review-in is used", file=sys.stderr)
        return 2

    try:
        jp_lines = load_srt(args.jp_srt)
        en_lines = load_srt(args.en_srt)
    except SrtDependencyError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    jp_lines = _prepare_lines(jp_lines, gap_ms=args.gap_merge_ms, drop_sfx=not args.keep_sfx)
    en_lines = _prepare_lines(en_lines, gap_ms=args.gap_merge_ms, drop_sfx=not args.keep_sfx)

    if args.limit and args.limit > 0:
        jp_lines = jp_lines[: args.limit]

    en_texts = align_by_overlap(jp_lines, en_lines)

    if args.review_out:
        provider = args.llm_provider
        api_key = _resolve_api_key(provider, args.llm_api_key)
        api_base = _resolve_api_base(provider, args.llm_api_base.strip())
        endpoint = _resolve_endpoint(provider, args.llm_endpoint.strip())

        if not api_key:
            print(
                "LLM API key is required for --review-out (set --llm-api-key, LLM_API_KEY, or provider-specific key)",
                file=sys.stderr,
            )
            return 2

        level = args.user_level
        if level == "middle":
            level = "intermediate"

        llm_items = [
            LlmItem(line_id=idx, jp=jp_line.text, en=en_text)
            for idx, (jp_line, en_text) in enumerate(zip(jp_lines, en_texts), start=1)
        ]
        config = LlmConfig(
            model=args.llm_model,
            api_key=api_key,
            provider=provider,
            api_base=api_base,
            endpoint=endpoint,
            temperature=args.llm_temperature,
            batch_size=args.llm_batch_size,
            timeout_s=args.llm_timeout,
            level=level,
            reasoning_effort=args.llm_reasoning_effort,
            app_name=args.llm_app_name.strip(),
            site_url=args.llm_site_url.strip(),
            anthropic_version=args.llm_anthropic_version,
            debug=args.llm_debug,
            debug_file=args.llm_debug_file,
        )

        try:
            selections = select_candidates(llm_items, config)
        except LlmError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        selection_map = {sel.line_id: sel for sel in selections}
        review_rows: List[ReviewRow] = []
        for idx, (jp_line, en_text) in enumerate(zip(jp_lines, en_texts), start=1):
            selection = selection_map.get(idx)
            llm_keep = selection.keep if selection else False
            focus = selection.focus if selection else ""
            gloss = selection.gloss if selection else ""
            reason = selection.reason if selection else ""
            review_rows.append(
                ReviewRow(
                    line_id=idx,
                    start_ms=jp_line.start_ms,
                    end_ms=jp_line.end_ms,
                    jp=jp_line.text,
                    en=en_text,
                    level=level,
                    llm_keep=llm_keep,
                    approved=llm_keep,
                    focus=focus,
                    gloss=gloss,
                    reason=reason,
                    notes="",
                )
            )

        review_path = os.path.abspath(args.review_out)
        write_review_tsv(review_rows, review_path)
        print(f"Wrote review file to {review_path}")
        print("Edit the 'approved' column, then re-run with --review-in to generate cards.")
        return 0

    out_dir = os.path.abspath(args.out_dir)
    audio_dir = os.path.join(out_dir, "media", "audio")
    image_dir = os.path.join(out_dir, "media", "img")
    ensure_dir(audio_dir)
    ensure_dir(image_dir)

    cards: List[CardLine] = []
    for idx, (jp_line, en_text) in enumerate(zip(jp_lines, en_texts), start=1):
        try:
            romaji = romaji_text(jp_line.text)
        except TextDependencyError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        audio_file = f"audio_{idx:05d}.mp3"
        image_file = f"img_{idx:05d}.jpg"
        cards.append(
            CardLine(
                line_id=idx,
                start_ms=jp_line.start_ms,
                end_ms=jp_line.end_ms,
                jp=jp_line.text,
                en=en_text,
                romaji=romaji,
                audio_file=audio_file,
                image_file=image_file,
                source=os.path.basename(args.video),
            )
        )

        if not args.dry_run:
            try:
                extract_audio(
                    args.video,
                    jp_line.start_ms,
                    jp_line.end_ms,
                    os.path.join(audio_dir, audio_file),
                    audio_track=args.audio_track,
                    pad_before_ms=args.pad_before_ms,
                    pad_after_ms=args.pad_after_ms,
                )
                mid_ms = int((jp_line.start_ms + jp_line.end_ms) / 2)
                extract_image(
                    args.video,
                    mid_ms,
                    os.path.join(image_dir, image_file),
                    video_track=args.video_track,
                )
            except MediaError as exc:
                print(f"Media extraction failed at line {idx}: {exc}", file=sys.stderr)
                return 1

    if args.format == "csv":
        out_path = export_csv(cards, out_dir)
    else:
        out_path = export_apkg(cards, out_dir, deck_name=args.deck_name)

    print(f"Wrote {len(cards)} cards to {out_path}")
    return 0
