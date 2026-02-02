from __future__ import annotations

from typing import List

from .models import SubtitleLine


class MissingDependencyError(RuntimeError):
    pass


def load_srt(path: str) -> List[SubtitleLine]:
    try:
        import pysubs2
    except ImportError as exc:
        raise MissingDependencyError(
            "pysubs2 is required for subtitle parsing. Install with: pip install pysubs2"
        ) from exc

    subs = pysubs2.load(path)
    lines = [SubtitleLine(start_ms=s.start, end_ms=s.end, text=s.text) for s in subs]
    lines.sort(key=lambda line: (line.start_ms, line.end_ms))
    return lines


def merge_adjacent(lines: List[SubtitleLine], gap_ms: int) -> List[SubtitleLine]:
    if not lines:
        return []
    merged: List[SubtitleLine] = [lines[0]]
    for line in lines[1:]:
        prev = merged[-1]
        gap = line.start_ms - prev.end_ms
        if gap <= gap_ms:
            combined_text = f"{prev.text} {line.text}".strip()
            merged[-1] = SubtitleLine(
                start_ms=prev.start_ms,
                end_ms=max(prev.end_ms, line.end_ms),
                text=combined_text,
            )
        else:
            merged.append(line)
    return merged
