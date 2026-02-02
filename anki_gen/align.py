from __future__ import annotations

from typing import Iterable, List

from .models import SubtitleLine


def _overlap_ms(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def align_by_overlap(
    jp_lines: Iterable[SubtitleLine],
    en_lines: List[SubtitleLine],
    tolerance_ms: int = 150,
) -> List[str]:
    aligned: List[str] = []
    en_index = 0

    for jp in jp_lines:
        candidates: List[SubtitleLine] = []
        while en_index < len(en_lines) and en_lines[en_index].end_ms < jp.start_ms - tolerance_ms:
            en_index += 1

        scan = en_index
        while scan < len(en_lines) and en_lines[scan].start_ms <= jp.end_ms + tolerance_ms:
            overlap = _overlap_ms(jp.start_ms, jp.end_ms, en_lines[scan].start_ms, en_lines[scan].end_ms)
            if overlap > 0:
                candidates.append(en_lines[scan])
            scan += 1

        if not candidates:
            aligned.append("")
        else:
            joined = " ".join(line.text for line in candidates)
            aligned.append(joined)
    return aligned
