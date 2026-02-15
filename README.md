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

Show full grouped help (with color in interactive terminals):

```bash
python -m anki_gen --help
```

You can force or disable ANSI coloring via `--color always` / `--color never`.

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

Set `--llm-api-key` (or env) to enable the LLM step.
Set `OPENAI_MODEL` to change the default model globally.
The CLI also auto-loads a `.env` file from the current working directory.
Use `--llm-provider` to switch API providers (`openai`, `openrouter`, `anthropic`).

Example `.env`:

```bash
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5-mini
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_ENDPOINT=/chat/completions
OPENAI_TEMPERATURE=1.0
OPENAI_REASONING_EFFORT=minimal
OPENAI_DEBUG_FILE=output/llm_debug.log
LLM_PROVIDER=openai
LLM_MODEL=gpt-5-mini
LLM_API_KEY=
LLM_API_BASE=
LLM_API_ENDPOINT=
LLM_TEMPERATURE=1.0
LLM_REASONING_EFFORT=minimal
LLM_DEBUG_FILE=output/llm_debug.log
OPENROUTER_API_KEY=
OPENROUTER_APP_NAME=anki-gen
OPENROUTER_SITE_URL=https://example.com
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_API_ENDPOINT=/chat/completions
ANTHROPIC_API_KEY=
ANTHROPIC_API_BASE=https://api.anthropic.com/v1
ANTHROPIC_API_ENDPOINT=/messages
ANTHROPIC_VERSION=2023-06-01
```

Provider examples:

```bash
# OpenAI (default)
python -m anki_gen ... --llm-provider openai --llm-model gpt-5-mini

# OpenRouter (OpenAI-compatible endpoint)
python -m anki_gen ... --llm-provider openrouter --llm-model openai/gpt-5-mini

# Anthropic
python -m anki_gen ... --llm-provider anthropic --llm-model claude-3-5-sonnet-latest
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
