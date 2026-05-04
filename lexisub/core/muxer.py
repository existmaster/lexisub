from __future__ import annotations
import subprocess
from pathlib import Path
from lexisub.core.audio import ffmpeg_path  # re-export for tests


def mux_subtitle(
    video_path: Path,
    srt_path: Path,
    out_path: Path,
    language: str = "kor",
    title: str = "Korean",
) -> Path:
    """Mux SRT into MKV with stream-copy (no re-encoding)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_path(), "-y",
        "-i", str(video_path),
        "-i", str(srt_path),
        "-map", "0:v", "-map", "0:a?", "-map", "1:0",
        "-c", "copy",
        "-c:s", "srt",
        "-metadata:s:s:0", f"language={language}",
        "-metadata:s:s:0", f"title={title}",
        "-loglevel", "error",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return out_path
