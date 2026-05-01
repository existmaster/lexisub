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
uv run pytest                       # quick (35 tests, skips heavy)
uv run pytest -m heavy              # 3 model-download tests (~4GB, slow)
```

## Requirements
- Python 3.12, Apple Silicon Mac, ffmpeg (`brew install ffmpeg`)

## Status (MVP v0.1.0-rc)

Tasks 1–15 of `business/work/독진수-mma-자막-앱/2026-05-01-plan-mvp.md` complete:

- Project bootstrap, config, SQLite glossary DB
- SRT parsing/serialization (pure)
- Glossary CSV import + system-prompt builder
- Translator chunking with timestamp preservation (pure)
- ffmpeg audio extraction + subtitle mux (stream copy, no re-encoding)
- mlx-whisper STT wrapper (large-v3-turbo)
- mlx-lm translation wrapper (Gemma 3 4B 4-bit) with glossary injection + retry
- End-to-end pipeline orchestration with sequential model loading (8GB-safe)
- PySide6 GUI: main window, video processing tab (drag-drop + worker thread), glossary tab (CSV import + approve toggle)

35 quick tests passing, 3 heavy tests deferred to manual verification.

## Pending: Task 16 — Manual end-to-end verification

The following must be done on the trainer's machine (or any M1 Mac with internet):

1. **Heavy test run** (downloads ~4GB the first time):
   ```
   uv run pytest -m heavy
   ```
   Expected: 3 passed (STT, translator, pipeline). First run takes 5–15 minutes.

2. **GUI manual verification**:
   ```
   uv run mma-sub
   ```
   - Window opens with two tabs (영상 처리 / 용어집).
   - Glossary tab: import `tests/fixtures/glossary.csv` → 4 rows shown. Double-click toggles status.
   - Video tab: drag `tests/fixtures/sample_speech.mp4` → progress bar advances through stages.
   - Output `sample_speech.ko.srt` and `sample_speech.subbed.mkv` produced beside the input.
   - Open `.mkv` in VLC: subtitle track present and selectable, "가드 패스" appears in Korean text.

3. **Tag release** once verified:
   ```
   git tag -a v0.1.0 -m "MVP: video → Korean subtitles with manual glossary"
   ```

## Known limitations (deferred to later versions)
- No PDF auto-extraction (v0.2)
- No subtitle preview/edit GUI (v0.3)
- No job queue / history view (v0.3)
- No `.app` packaging (v1.0)
