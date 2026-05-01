from __future__ import annotations
import shutil
import subprocess
from pathlib import Path


class FfmpegMissingError(RuntimeError):
    pass


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise FfmpegMissingError(
            "ffmpeg not found. Install: brew install ffmpeg"
        )


def extract_wav(video_path: Path, out_path: Path) -> Path:
    _require_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-ac", "1", "-ar", "16000", "-vn",
        "-loglevel", "error",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return out_path
