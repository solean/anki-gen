# Anki Gen MVP

Generate Anki cards from a video plus Japanese/English subtitles.

## Requirements
- Python 3.9+
- `ffmpeg` on PATH

Install Python deps:

```bash
pip install -r requirements.txt
```

## Usage

```bash
python -m anki_gen \
  --video "path/to/video.mkv" \
  --jp-srt "path/to/jp.srt" \
  --en-srt "path/to/en.srt" \
  --out-dir output \
  --format csv
```

For Anki packages:

```bash
python -m anki_gen \
  --video "path/to/video.mkv" \
  --jp-srt "path/to/jp.srt" \
  --en-srt "path/to/en.srt" \
  --out-dir output \
  --format apkg \
  --deck-name "Frieren S01E08"
```

## Notes
- Output media goes in `output/media/audio` and `output/media/img`.
- The CSV export is a tab-separated file (`cards.tsv`).
