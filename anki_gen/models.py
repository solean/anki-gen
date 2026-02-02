from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleLine:
    start_ms: int
    end_ms: int
    text: str


@dataclass
class CardLine:
    line_id: int
    start_ms: int
    end_ms: int
    jp: str
    en: str
    romaji: str
    audio_file: str
    image_file: str
    source: str

    @property
    def start_seconds(self) -> float:
        return self.start_ms / 1000.0

    @property
    def end_seconds(self) -> float:
        return self.end_ms / 1000.0
