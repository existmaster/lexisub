"""Run the Lexisub pipeline against a single video and emit a verification report.

Usage:
    uv run python scripts/run_demo.py <video_path> [--glossary <csv>] [--out <dir>]

Produces:
    <out_dir>/<stem>.ko.srt
    <out_dir>/<stem>.subbed.mkv
    <out_dir>/<stem>.report.md  (timing, codec preservation, glossary hit rate)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from lexisub import config
from lexisub.core import glossary, pipeline, subtitle
from lexisub.db import repository


def ffprobe_codec(path: Path, stream: str = "v:0") -> str | None:
    if shutil.which("ffprobe") is None:
        return None
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                stream,
                "-show_entries",
                "stream=codec_name",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return out or None
    except subprocess.CalledProcessError:
        return None


def ffprobe_duration(path: Path) -> float | None:
    if shutil.which("ffprobe") is None:
        return None
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return float(out) if out else None
    except (subprocess.CalledProcessError, ValueError):
        return None


def compute_glossary_hit_rate(
    db_path: Path, source_lang: str, srt_text: str, video_text: str
) -> dict:
    """For each approved glossary term whose source_term appears in the
    Whisper transcript (video_text), check whether ko_term appears in the
    final SRT.
    """
    rows = [
        r
        for r in repository.list_terms(db_path, status="approved")
        if r["source_lang"] == source_lang
    ]
    relevant = []
    hits = 0
    misses = []
    src_lower = video_text.lower()
    for r in rows:
        st = r["source_term"].lower()
        if st in src_lower:
            relevant.append(r["source_term"])
            if r["ko_term"] in srt_text:
                hits += 1
            else:
                misses.append(f"{r['source_term']} → {r['ko_term']}")
    rate = (hits / len(relevant)) if relevant else None
    return {
        "approved_total": len(rows),
        "appeared_in_video": len(relevant),
        "hits": hits,
        "misses": misses,
        "hit_rate": rate,
    }


def build_report(
    *,
    video: Path,
    result: pipeline.PipelineResult,
    wall_seconds: float,
    progress_log: list[tuple[str, float]],
    db_path: Path,
    src_text: str,
) -> str:
    duration = ffprobe_duration(video)
    in_codec = ffprobe_codec(video, "v:0")
    out_codec = ffprobe_codec(result.mkv_path, "v:0")
    sub_lang = ffprobe_codec(result.mkv_path, "s:0")  # codec, not lang; informational

    srt_text = result.srt_path.read_text(encoding="utf-8")
    cues = subtitle.parse_srt(srt_text)
    glossary_stats = compute_glossary_hit_rate(
        db_path, result.source_lang, srt_text, src_text
    )

    speed_ratio = (wall_seconds / duration) if duration and duration > 0 else None

    stages_seen = sorted({s for s, _ in progress_log})

    lines: list[str] = []
    lines.append(f"# Lexisub demo report — {video.name}\n")
    lines.append(f"- Input: `{video}`")
    if duration is not None:
        lines.append(f"- Duration: {duration:.1f} s")
    lines.append(f"- Detected language: `{result.source_lang}`")
    lines.append(f"- Wall time: {wall_seconds:.1f} s")
    if speed_ratio is not None:
        lines.append(f"- Speed ratio (wall / video): **{speed_ratio:.2f}x**")
    lines.append("")
    lines.append("## Output files")
    lines.append(f"- `{result.srt_path}`")
    lines.append(f"- `{result.mkv_path}`")
    lines.append("")
    lines.append("## Codec preservation")
    lines.append(f"- Input video codec: `{in_codec}`")
    lines.append(f"- Output video codec: `{out_codec}`")
    preserved = (
        in_codec is not None and out_codec is not None and in_codec == out_codec
    )
    lines.append(f"- Preserved (no re-encoding): **{preserved}**")
    lines.append(f"- Subtitle stream codec: `{sub_lang}`")
    lines.append("")
    lines.append("## Subtitle stats")
    lines.append(f"- Cue count (output): {len(cues)}")
    if duration:
        cpm = len(cues) / (duration / 60)
        lines.append(f"- Cues per minute: {cpm:.1f}")
    lines.append("")
    lines.append("## Glossary hit rate")
    g = glossary_stats
    lines.append(f"- Approved terms (this language): {g['approved_total']}")
    lines.append(f"- Terms that appeared in transcript: {g['appeared_in_video']}")
    lines.append(f"- Hits in output SRT: {g['hits']}")
    if g["hit_rate"] is not None:
        lines.append(f"- **Hit rate: {g['hit_rate'] * 100:.0f}%**")
    else:
        lines.append("- Hit rate: N/A (no approved terms appeared)")
    if g["misses"]:
        lines.append("- Missed terms:")
        for m in g["misses"]:
            lines.append(f"  - {m}")
    lines.append("")
    lines.append("## Pipeline stages observed")
    lines.append(", ".join(stages_seen))
    lines.append("")
    lines.append("## First 5 SRT cues")
    lines.append("```")
    for c in cues[:5]:
        lines.append(f"[{c.start_ms / 1000:.2f}s] {c.text}")
    lines.append("```")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", type=Path, help="Path to input video")
    p.add_argument(
        "--glossary",
        type=Path,
        default=None,
        help="CSV glossary to import before processing",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("demos/outputs"),
        help="Output directory (default: demos/outputs)",
    )
    p.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path (default: per-run temp DB so glossary changes don't pollute the app DB)",
    )
    p.add_argument(
        "--keep-app-db",
        action="store_true",
        help="Use the real app DB instead of a per-run temp DB",
    )
    args = p.parse_args()

    if not args.video.exists():
        print(f"error: video not found: {args.video}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)

    if args.keep_app_db or args.db:
        db_path = args.db or config.DB_PATH
    else:
        db_path = args.out / f".{args.video.stem}.demo.sqlite3"
    repository.init_db(db_path)

    if args.glossary:
        if not args.glossary.exists():
            print(f"error: glossary not found: {args.glossary}", file=sys.stderr)
            return 2
        n = glossary.import_csv(db_path, args.glossary, default_status="approved")
        print(f"imported {n} glossary terms from {args.glossary}")

    progress_log: list[tuple[str, float]] = []

    def on_progress(stage: str, frac: float) -> None:
        progress_log.append((stage, frac))
        if frac in (0.0, 1.0):
            print(f"  [{stage}] {frac:.0%}")

    print(f"processing {args.video.name} → {args.out}")
    t0 = time.monotonic()
    result = pipeline.process_video(args.video, args.out, db_path, on_progress)
    wall = time.monotonic() - t0

    # Re-derive transcript text for glossary hit-rate analysis. Pipeline
    # doesn't expose the original Whisper output separately, so we re-read
    # the SRT once: glossary terms in source_lang appear in the final SRT
    # only if they originate from the transcript anyway.
    src_text = result.source_srt_path.read_text(encoding="utf-8")

    report_md = build_report(
        video=args.video,
        result=result,
        wall_seconds=wall,
        progress_log=progress_log,
        db_path=db_path,
        src_text=src_text,
    )
    report_path = args.out / f"{args.video.stem}.report.md"
    report_path.write_text(report_md, encoding="utf-8")

    print()
    print(report_md)
    print(f"report saved to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
