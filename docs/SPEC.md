# Video-to-Anki Generator Spec

## Goal
Generate Anki cards from video dialogue with synchronized audio, screenshot, Japanese text, romaji, and English translation.

## Inputs
- Video file (e.g., `.mkv`) with JP audio.
- Subtitles: JP and EN `.srt` (or embedded tracks) are assumed available.
- Config: target deck name, output dir, audio track index, filters, output format.

## Outputs
- Anki deck (`.apkg`) or CSV + media folder (configurable).
- Media files: `audio_<id>.mp3`, `img_<id>.jpg`.
- Manifest/log for traceability.

## Card Fields
- `JP` (cleaned subtitle line)
- `Romaji`
- `EN` (from subs or MT)
- `Audio` (Anki `[sound:...]`)
- `Image`
- `Start`, `End`, `Source` (optional tags/metadata)

## Pipeline
1. Ingest & Probe
   - Use `ffprobe` to read streams; select JP audio + subtitle track.
2. Subtitle Extraction
   - If external `.srt` exists, load directly; else extract from MKV (`ffmpeg -map 0:s`).
   - Parse with `pysubs2` to get `(start, end, text)`.
3. Line Filtering & Merging
   - Default: drop SFX-only lines (e.g., `（足音）`, `♪`) and allow override to keep/tag.
   - Merge short adjacent lines by gap threshold (e.g., `< 400ms`).
   - Normalize text: strip brackets, remove extra whitespace.
4. Media Extraction
   - Audio clip: `ffmpeg -ss start-0.1 -to end+0.2`.
   - Screenshot: sample mid-time; `ffmpeg -ss mid -vframes 1`.
5. Text Processing
   - Romaji: `pykakasi` or `fugashi` + `unidic` (more accurate readings).
   - EN: align with existing EN subs by timestamp overlap; no MT in MVP.
6. Packaging
   - Use `genanki` or write CSV; copy media files to Anki media dir in `.apkg`.
   - Add tags: show, episode, scene, speaker (if available later).
7. Review/QA (optional)
   - Generate a review HTML/CSV for manual veto before final deck.

## Tech Stack (MVP)
- Python CLI
- `ffmpeg`, `ffprobe`
- `pysubs2`
- `pykakasi` (romaji) or `fugashi` + `unidic`
- `genanki`
- Translation provider plugin (local or API)

## Data Model (per line)
```
id, start_ms, end_ms, text_jp, text_romaji, text_en, audio_path, image_path, source
```

## Risks / Edge Cases
- Subtitle timing mismatch with audio; variable framerate.
- SFX lines; multi-speaker subtitles.
- MT quality for short fragments; lack of context.
- Embedded subtitle encoding issues (full-width punctuation, ruby tags).

## Plan / Milestones
1. MVP (SRT-driven)
   - Parse JP `.srt`, generate romaji, export CSV with dummy EN.
   - Extract audio + image per line.
2. Subtitle Alignment
   - Align JP and EN lines by timestamp overlap; handle many-to-one by best overlap.
3. Quality Pass
   - Line merging rules, SFX filtering, adjustable padding.
   - Simple review step (approve/reject list).
4. Optional: No-Subtitle Mode
   - Whisper/WhisperX transcription with timestamps.
   - Add speaker diarization later if needed.

## Open Questions
1. Do you want `.apkg` generation or CSV + media for manual import (or support both)?
2. How aggressive should we be in filtering SFX/narration lines beyond the default drop-SFX-only?
