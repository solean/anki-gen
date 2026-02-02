from __future__ import annotations

import argparse
import os
import sys
from typing import List

from .align import align_by_overlap
from .export import export_apkg, export_csv
from .media import ensure_dir, extract_audio, extract_image, MediaError
from .models import CardLine, SubtitleLine
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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Anki cards from video + JP/EN subtitles")
    parser.add_argument("--video", required=True, help="Path to the video file")
    parser.add_argument("--jp-srt", required=True, help="Path to Japanese .srt")
    parser.add_argument("--en-srt", required=True, help="Path to English .srt")
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
    parser.add_argument("--dry-run", action="store_true", help="Skip media extraction")
    return parser


def main(argv: List[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

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
