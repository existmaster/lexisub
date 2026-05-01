# MMA Subtitle Tool

Local desktop app: video → Korean subtitles, MMA glossary applied.

Built for 독진수 trainer. M1 Mac (Apple Silicon) only.

## Setup
```
uv sync
uv run mma-sub
```

## Tests
```
uv run pytest                       # quick (skips heavy)
uv run pytest -m heavy              # model-download tests
```

## Requirements
- Python 3.12, Apple Silicon Mac, ffmpeg (`brew install ffmpeg`)
