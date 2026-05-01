# Lexisub

Local desktop app: any video → Korean subtitles, with your own custom glossary applied so domain terms get translated consistently.

Built and tested for MMA training videos initially (the trainer 독진수's use case), but works for any domain — medical lectures, legal seminars, technical tutorials — by importing your own term glossary.

Apple Silicon Mac only. Runs entirely locally; no cloud API calls.

## Setup
```
uv sync
uv run lexisub
```

## How it works
1. Drop a video into the app.
2. Local Whisper (mlx-whisper large-v3-turbo) transcribes it.
3. Local Gemma 3 4B (mlx-lm) translates each line to Korean, with your approved glossary terms forced verbatim.
4. The Korean `.srt` is written next to the video, and an `.mkv` with the subtitle track muxed in is produced (no re-encoding).

## Glossary
- Import a CSV with columns `source_lang, source_term, ko_term, category` from the 용어집 tab.
- Approved terms are injected into the translator's system prompt — they will be used as-is in the output.
- Example: `tests/fixtures/glossary.csv` has 4 MMA grappling terms.

## Tests
```
uv run pytest                       # quick (35 tests, skips heavy)
uv run pytest -m heavy              # 3 model-download tests (~4GB, slow)
```

## Requirements
- Apple Silicon Mac (M1/M2/M3/M4)
- Python 3.12 (auto-installed by uv)
- ffmpeg: `brew install ffmpeg`
- Internet on first run (~4GB models auto-download to HuggingFace cache)
- ~6GB free disk

## Known limitations
- Korean output only (other target languages are roadmap)
- No GUI for editing subtitles before mux (next milestone)
- No PDF auto-extraction of glossaries yet (next milestone)

## Build a standalone .app (advanced)

For redistributing to non-developers (no Python/uv required on their Mac):

```
uv sync --all-extras       # ensure pyinstaller is installed
./scripts/build_app.sh
# Output: dist/Lexisub.app  (~400-600MB, unsigned)
```

To run on another Apple Silicon Mac:
```
xattr -dr com.apple.quarantine /path/to/Lexisub.app
open /path/to/Lexisub.app
```

The .app does NOT bundle the ~4GB ML models — they download on first run to `~/.cache/huggingface/`.

The .app is unsigned. macOS Gatekeeper will warn on first launch; either right-click → Open, or run the `xattr` command above to remove the quarantine attribute.

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Note: this software downloads and uses Google's Gemma model on first run. Use of the model is governed by the [Gemma Terms of Use](https://ai.google.dev/gemma/terms), independent of this project's Apache 2.0 license.
