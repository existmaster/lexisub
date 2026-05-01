# Lexisub

Local desktop app: any video → Korean subtitles, with your own custom glossary applied so domain terms get translated consistently.

Built and tested for MMA training videos initially (the trainer 독진수's use case), but works for any domain — medical lectures, legal seminars, technical tutorials — by importing your own term glossary.

Apple Silicon Mac only. Runs entirely locally; no cloud API calls.

## Install (recommended for end users)

Download the latest pre-built `.app` zip from [Releases](https://github.com/existmaster/lexisub/releases/latest), then:

```bash
unzip Lexisub-v*-macos-arm64.zip
xattr -dr com.apple.quarantine Lexisub.app
open Lexisub.app
```

The `.app` is unsigned (no Apple Developer signature). macOS will warn on first launch — use the `xattr` command above, or right-click the app and choose **Open** the first time.

You also need `ffmpeg`:
```bash
brew install ffmpeg
```

On first run, the app downloads ~4GB of ML models (Whisper + Gemma 3 4B) to `~/.cache/huggingface/`. Subsequent launches are instant.

## Run from source (developers)
```
uv sync
uv run lexisub
```

## How it works
1. Drop a video into the app.
2. Local Whisper (mlx-whisper large-v3-turbo) transcribes it.
3. Local Gemma 3 4B (mlx-lm) translates each line to Korean, with your approved glossary terms forced verbatim.
4. The Korean `.srt` is written next to the video, and an `.mkv` with the subtitle track muxed in is produced (no re-encoding).

## Glossary workflow

You have two ways to populate the glossary:

### A. Auto-extract from PDFs (recommended)
1. **PDF 라이브러리** tab → [PDF 추가] → select one or more PDFs (textbooks, course notes, etc.). Source language defaults to **자동 감지** (the PDF's dominant language is detected with `langdetect`); override via the dropdown if needed.
2. The app extracts text via PyMuPDF and asks the local Gemma 3 model to identify domain terms, generating Korean translations. The LLM also tags each term with its own `source_lang`, so multilingual PDFs (e.g. Korean textbooks with English medical terms) yield terms tagged in different languages automatically.
3. New terms land in the **용어집** tab with status `pending`.
4. Review and approve them (double-click toggles approved ↔ pending).
5. Approved terms are forced verbatim during video translation (only those whose `source_lang` matches the video's detected language).

### B. CSV import (for existing glossaries)
- 용어집 tab → [CSV 가져오기] → select a CSV with columns
  `source_lang, source_term, ko_term, category`.
- Imported terms land as `approved` by default.
- Examples in `demos/glossaries/`.

## Tests
```
uv run pytest                       # quick (44 tests, skips heavy)
uv run pytest -m heavy              # 4 model-download tests (~4GB, slow)
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
- Not packaged signed (`.app` is unsigned — quarantine workaround documented above)

## Build a standalone .app from source (advanced)

You normally don't need this — pre-built zips are on the [Releases](https://github.com/existmaster/lexisub/releases) page, auto-built by GitHub Actions on every tag push (see `.github/workflows/build-app.yml`).

If you do want to build locally:
```
uv sync --all-extras
./scripts/build_app.sh
# Output: dist/Lexisub.app  (~800MB, unsigned)
```

To cut a new release (which auto-publishes a `.app` zip):
```
git tag -a v0.X.Y -m "release notes"
git push origin v0.X.Y
# Watch the build:  gh run watch
# Once green, the zip appears on the release page automatically.
```

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Note: this software downloads and uses Google's Gemma model on first run. Use of the model is governed by the [Gemma Terms of Use](https://ai.google.dev/gemma/terms), independent of this project's Apache 2.0 license.
