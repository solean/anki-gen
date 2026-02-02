from __future__ import annotations

import os
import subprocess


class MediaError(RuntimeError):
    pass


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise MediaError(result.stderr.strip() or "ffmpeg failed")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def extract_audio(
    video_path: str,
    start_ms: int,
    end_ms: int,
    output_path: str,
    audio_track: int,
    pad_before_ms: int,
    pad_after_ms: int,
) -> None:
    start = max(0, start_ms - pad_before_ms) / 1000.0
    end = (end_ms + pad_after_ms) / 1000.0

    args = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-ss",
        f"{start:.3f}",
        "-to",
        f"{end:.3f}",
        "-i",
        video_path,
        "-map",
        f"0:a:{audio_track}",
        "-ac",
        "1",
        "-ar",
        "44100",
        "-vn",
        output_path,
    ]
    _run_ffmpeg(args)


def extract_image(
    video_path: str,
    timestamp_ms: int,
    output_path: str,
    video_track: int,
) -> None:
    timestamp = max(0, timestamp_ms) / 1000.0
    args = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        video_path,
        "-map",
        f"0:v:{video_track}",
        "-frames:v",
        "1",
        "-q:v",
        "2",
        output_path,
    ]
    _run_ffmpeg(args)
