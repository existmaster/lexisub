from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from lexisub.core.audio import FfmpegMissingError


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise FfmpegMissingError("ffmpeg not found")


def mux_subtitle(
    video_path: Path,
    srt_path: Path,
    out_path: Path,
    language: str = "kor",
    title: str = "Korean",
) -> Path:
    """Mux SRT into MKV with stream-copy (no re-encoding)."""
    _require_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(srt_path),
        "-map", "0:v", "-map", "0:a?", "-map", "1:0",
        "-c", "copy",
        "-c:s", "srt",
        f"-metadata:s:s:0", f"language={language}",
        f"-metadata:s:s:0", f"title={title}",
        "-loglevel", "error",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return out_path
