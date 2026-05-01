# Demo Videos

This directory is for **user-provided** demo videos used to exercise Lexisub against real-world content. Videos placed under `demos/videos/` and outputs under `demos/outputs/` are gitignored — they don't ship with the repo.

For automated unit/integration tests, see `tests/fixtures/` (which contains a tiny synthetic `sample_speech.mp4` generated via macOS `say` for reproducible CI).

For end-user stories and acceptance criteria, see `tests/USER_STORIES.md`.

## How to add a demo video

```bash
mkdir -p demos/videos demos/outputs
# Copy or download your video into demos/videos/
cp ~/Downloads/some-bjj-tutorial.mp4 demos/videos/

# Run the pipeline against it
uv run python scripts/run_demo.py demos/videos/some-bjj-tutorial.mp4

# Output:
# - demos/outputs/some-bjj-tutorial.ko.srt
# - demos/outputs/some-bjj-tutorial.subbed.mkv
# - demos/outputs/some-bjj-tutorial.report.md
```

## Where to source legitimate demo videos

Lexisub's repo is public (Apache 2.0), but **demo video copyright belongs to the original creators**. Do not commit copyrighted videos. Below are sources where short clips are usable for personal testing:

### Creative Commons / Public Domain
- **YouTube (filter: Creative Commons)** — In YouTube search, use "Filters → Creative Commons". Many small BJJ/MMA channels release CC-BY content. Verify the license on the video page before downloading.
- **Wikimedia Commons** — Some martial-arts demonstration videos exist (sparse but free).
- **Pixabay / Pexels** — Stock video; some MMA training stock clips available.

### Personal use (don't redistribute)
- **Your own recordings** — Best option. Record a short coaching clip and use it.
- **Purchased courses** — If you bought a JJ Globetrotters / BJJ Fanatics class, processing it for your own captioning is fine; do not commit the video.

### Recommended channels with permissive content (verify license per video)
- *Stephan Kesting* (Grapplearts) — many short tutorial clips
- *Jiu-Jitsu X* — instructional content
- Several MMA federations release press conferences under permissive terms

### yt-dlp helper

If you have permission and need to fetch a short clip:

```bash
# 720p, max 5 minutes (use --download-sections "*0:00-5:00" for clipping)
yt-dlp -f "bv*[height<=720]+ba/b[height<=720]" \
       --download-sections "*0:00-5:00" \
       -o "demos/videos/%(title)s.%(ext)s" \
       "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
```

> ⚠️ Verify license on the YouTube page. Personal-use downloads are not redistribution; commiting them to a public repo IS redistribution.

## Glossaries

`demos/glossaries/` contains example glossaries you can import via the GUI's [CSV 가져오기] or pass to `run_demo.py`:

- `bjj.csv` — common BJJ grappling terms (in/around 30 entries)
- `striking.csv` — boxing/Muay Thai/MMA striking terms
- `general.csv` — broad MMA/training vocabulary

Import via:
- GUI: 용어집 탭 → [CSV 가져오기]
- CLI: `uv run python scripts/run_demo.py <video> --glossary demos/glossaries/bjj.csv`
