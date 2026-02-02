from __future__ import annotations

import csv
import hashlib
import os
from typing import Iterable, List

from .models import CardLine


class MissingDependencyError(RuntimeError):
    pass


def export_csv(cards: Iterable[CardLine], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "cards.tsv")

    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, dialect="excel-tab")
        writer.writerow(["JP", "Romaji", "EN", "Audio", "Image", "Start", "End", "Source"])
        for card in cards:
            audio = f"[sound:{card.audio_file}]" if card.audio_file else ""
            image = f"<img src=\"{card.image_file}\">" if card.image_file else ""
            writer.writerow(
                [
                    card.jp,
                    card.romaji,
                    card.en,
                    audio,
                    image,
                    card.start_ms,
                    card.end_ms,
                    card.source,
                ]
            )
    return out_path


def _stable_id(seed: str) -> int:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return int(digest[:10], 16)


def export_apkg(cards: List[CardLine], out_dir: str, deck_name: str) -> str:
    try:
        import genanki
    except ImportError as exc:
        raise MissingDependencyError(
            "genanki is required for apkg export. Install with: pip install genanki"
        ) from exc

    os.makedirs(out_dir, exist_ok=True)
    deck_id = _stable_id(f"anki-gen-deck-{deck_name}")
    model_id = _stable_id(f"anki-gen-model-{deck_name}")

    model = genanki.Model(
        model_id,
        "AnkiGenModel",
        fields=[
            {"name": "JP"},
            {"name": "Romaji"},
            {"name": "EN"},
            {"name": "Audio"},
            {"name": "Image"},
            {"name": "Start"},
            {"name": "End"},
            {"name": "Source"},
        ],
        css="""
.card {
  font-family: "Avenir Next", "Noto Sans JP", "Hiragino Kaku Gothic ProN",
    "Yu Gothic", "Segoe UI", sans-serif;
  font-size: 20px;
  color: #f2f2f2;
  background: #2f2f2f;
}

.wrap {
  max-width: 720px;
  margin: 24px auto 32px;
  padding: 0 24px;
  text-align: center;
}

.scene {
  display: block;
  margin: 8px auto 18px;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  max-width: 100%;
  height: auto;
}

.jp {
  font-size: 24px;
  line-height: 1.5;
  margin: 16px 0 8px;
}

.romaji {
  font-size: 18px;
  opacity: 0.85;
  margin: 4px 0 12px;
}

.en {
  font-size: 20px;
  line-height: 1.5;
  margin: 12px 0 0;
  color: #d9d9d9;
}
""",
        templates=[
            {
                "name": "Card 1",
                "qfmt": (
                    "<div class='wrap'>"
                    "<div>{{Image}}</div>"
                    "<div class='jp'>{{JP}}</div>"
                    "<div class='romaji'>{{Romaji}}</div>"
                    "<div>{{Audio}}</div>"
                    "</div>"
                ),
                "afmt": (
                    "<div class='wrap'>"
                    "<div class='en'>{{EN}}</div>"
                    "</div>"
                ),
            }
        ],
    )

    deck = genanki.Deck(deck_id, deck_name)

    media_files: List[str] = []
    for card in cards:
        fields = [
            card.jp,
            card.romaji,
            card.en,
            f"[sound:{card.audio_file}]" if card.audio_file else "",
            f"<img class='scene' src=\"{card.image_file}\">" if card.image_file else "",
            str(card.start_ms),
            str(card.end_ms),
            card.source,
        ]
        note = genanki.Note(model=model, fields=fields)
        deck.add_note(note)
        if card.audio_file:
            media_files.append(os.path.join(out_dir, "media", "audio", card.audio_file))
        if card.image_file:
            media_files.append(os.path.join(out_dir, "media", "img", card.image_file))

    package = genanki.Package(deck)
    package.media_files = media_files
    out_path = os.path.join(out_dir, "deck.apkg")
    package.write_to_file(out_path)
    return out_path
