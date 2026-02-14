from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class ReviewRow:
    line_id: int
    start_ms: int
    end_ms: int
    jp: str
    en: str
    level: str
    llm_keep: bool
    approved: bool
    focus: str
    gloss: str
    reason: str
    notes: str


_FIELDS = [
    "line_id",
    "start_ms",
    "end_ms",
    "jp",
    "en",
    "level",
    "llm_keep",
    "approved",
    "focus",
    "gloss",
    "reason",
    "notes",
]


def _bool_to_str(value: bool) -> str:
    return "1" if value else "0"


def _parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "y", "t"}


def write_review_tsv(rows: Iterable[ReviewRow], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, dialect="excel-tab")
        writer.writerow(_FIELDS)
        for row in rows:
            writer.writerow(
                [
                    row.line_id,
                    row.start_ms,
                    row.end_ms,
                    row.jp,
                    row.en,
                    row.level,
                    _bool_to_str(row.llm_keep),
                    _bool_to_str(row.approved),
                    row.focus,
                    row.gloss,
                    row.reason,
                    row.notes,
                ]
            )


def load_review_tsv(path: str) -> List[ReviewRow]:
    with open(path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, dialect="excel-tab")
        rows: List[ReviewRow] = []
        for raw in reader:
            rows.append(
                ReviewRow(
                    line_id=int(raw.get("line_id", "0") or 0),
                    start_ms=int(raw.get("start_ms", "0") or 0),
                    end_ms=int(raw.get("end_ms", "0") or 0),
                    jp=raw.get("jp", "") or "",
                    en=raw.get("en", "") or "",
                    level=raw.get("level", "") or "",
                    llm_keep=_parse_bool(raw.get("llm_keep")),
                    approved=_parse_bool(raw.get("approved")),
                    focus=raw.get("focus", "") or "",
                    gloss=raw.get("gloss", "") or "",
                    reason=raw.get("reason", "") or "",
                    notes=raw.get("notes", "") or "",
                )
            )
        return rows
