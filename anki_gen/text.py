from __future__ import annotations

import re
from typing import List


_BRACKETED_LINE = re.compile(r"^[\(（\[【].*[\)）\]】]$")
_MUSIC_LINE = re.compile(r"^[♪♫].*$")
_LEADING_TAG = re.compile(r"^[\(（\[【].+?[\)）\]】]\s*(.+)$")


class MissingDependencyError(RuntimeError):
    pass


def is_sfx_only(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True
    for line in lines:
        if _BRACKETED_LINE.match(line) or _MUSIC_LINE.match(line):
            continue
        return False
    return True


def _strip_leading_tag(line: str) -> str:
    match = _LEADING_TAG.match(line)
    if match:
        return match.group(1).strip()
    return line


def normalize_text(text: str) -> str:
    # pysubs2 can preserve explicit line breaks as literal "\N"
    text = text.replace("\\N", "\n")
    parts: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts.append(_strip_leading_tag(line))
    joined = " ".join(parts)
    return " ".join(joined.split())


def romaji_text(text: str) -> str:
    try:
        from pykakasi import kakasi
    except ImportError as exc:
        raise MissingDependencyError(
            "pykakasi is required for romaji. Install with: pip install pykakasi"
        ) from exc

    converter = kakasi()
    converter.setMode("J", "a")
    converter.setMode("H", "a")
    converter.setMode("K", "a")
    converter.setMode("r", "Hepburn")
    converter.setMode("s", True)
    converter.setMode("C", True)
    converted = converter.getConverter().do(text)
    return " ".join(converted.split())
