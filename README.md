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

LLM-assisted review (two-step):

```bash
python -m anki_gen \
  --video "path/to/video.mkv" \
  --jp-srt "path/to/jp.srt" \
  --en-srt "path/to/en.srt" \
  --review-out output/review.tsv \
  --user-level beginner \
  --llm-model gpt-5-mini
```

Set `OPENAI_API_KEY` or pass `--llm-api-key` to enable the LLM step.
Set `OPENAI_MODEL` to change the default model globally.
The CLI also auto-loads a `.env` file from the current working directory.

Example `.env`:

```bash
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5-mini
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_ENDPOINT=/chat/completions
OPENAI_TEMPERATURE=1.0
OPENAI_REASONING_EFFORT=minimal
OPENAI_DEBUG_FILE=output/llm_debug.log
```

To debug LLM output formatting issues, add `--llm-debug` (stderr) and/or
`--llm-debug-file output/llm_debug.log`.

Edit `output/review.tsv` and flip the `approved` column, then generate cards:

```bash
python -m anki_gen \
  --video "path/to/video.mkv" \
  --review-in output/review.tsv \
  --out-dir output \
  --format apkg
```

With `--review-in`, card text uses reviewed fields:
- `JP` from `focus` (fallback: original `jp`)
- `EN` from `gloss` (fallback: `reason`, then original `en`)

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
