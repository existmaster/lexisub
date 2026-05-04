# Lexisub

Local desktop app: any video → Korean subtitles, with your own custom glossary applied so domain terms get translated consistently.

Built and tested for MMA training videos initially (the trainer 독진수's use case), but works for any domain — medical lectures, legal seminars, technical tutorials — by importing your own term glossary.

Apple Silicon Mac only. Runs entirely locally; no cloud API calls.

📖 **사용 설명서 (한국어)**: [USER_GUIDE.ko.md](USER_GUIDE.ko.md) — 처음 사용하시면 이쪽부터 읽어보세요. 워크플로우, GUI 기능, 자주 묻는 질문이 정리되어 있습니다.

## Install (recommended for end users)

[Releases 페이지](https://github.com/existmaster/lexisub/releases/latest)에서 **`Lexisub-vX.Y.Z-macos-arm64.dmg`** 다운로드.

1. DMG 더블클릭 → Finder 윈도우가 열림
2. Lexisub.app을 옆에 보이는 Applications 폴더로 드래그
3. 처음 한 번만: Applications에서 Lexisub 우클릭(Control+클릭) → **열기**
4. 첫 실행 시 약 4GB의 AI 모델 자동 다운로드 (한 번만, 이후 즉시 동작)

ffmpeg는 앱 안에 자동 포함됩니다 (별도 설치 불필요).

DMG 안에는 `사용설명서.html`도 들어 있어 더블클릭하면 한국어 가이드가 브라우저로 열립니다.

> **고급 사용자용**: zip 형태도 같이 첨부됩니다 (`Lexisub-vX.Y.Z-macos-arm64.zip`).
> 명령행 사용 시: `unzip ... && xattr -dr com.apple.quarantine Lexisub.app && open Lexisub.app`

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

## Managing the library

- **PDF 라이브러리** tab: select one or more PDFs and click [선택 제거]. Choose whether to also prune the auto-extracted *pending* terms whose only source was the removed PDF (your manually approved CSV terms are never touched).
- **용어집** tab: select rows and press <kbd>Delete</kbd> (or click [선택 삭제]) to remove specific terms. [출처 없는 보류 정리] sweeps any auto-extracted pending term that lost all its PDF sources.

## Tests
```
uv run pytest                       # quick (52 tests, skips heavy)
uv run pytest -m heavy              # 4 model-download tests (~4GB, slow)
```

## Optional: OCR for scanned PDFs

The default install does NOT include OCR (saves ~60MB on the .app bundle). If your PDFs are scans without a text layer, install the `ocr` extra:

```bash
uv sync --extra ocr
uv run python scripts/ocr_pdf.py "<scanned.pdf>"
# Produces <scanned>.ocr.pdf with a text layer; feed that into Lexisub.
```

This uses Apple Vision OCR (macOS native, free, ~2.5 pages/sec). Korean accuracy is excellent. The resulting `*.ocr.pdf` is what you import into the **PDF 라이브러리** tab.

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
uv sync --extra dev      # NOT --all-extras — keeps `ocr` out of the bundle
./scripts/build_app.sh
# Output: dist/Lexisub.app  (~600-700MB, unsigned)
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
