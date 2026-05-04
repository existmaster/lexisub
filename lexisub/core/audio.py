from __future__ import annotations
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


class FfmpegMissingError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def ffmpeg_path() -> str:
    """Return a usable ffmpeg binary path.

    Resolution order:
      1. ``imageio_ffmpeg`` bundled binary (always present once installed —
         ships in PyInstaller .app, no system install required)
      2. ``ffmpeg`` on $PATH (Homebrew, MacPorts, etc.)

    Raises FfmpegMissingError only if neither is available.
    """
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).exists():
            return bundled
    except Exception:
        pass
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    raise FfmpegMissingError(
        "ffmpeg를 찾을 수 없습니다.\n"
        "정상 배포본에는 자동 포함되어 있어야 합니다. "
        "소스로 실행 중이라면 `uv sync`로 의존성을 설치하거나 "
        "`brew install ffmpeg`로 시스템 설치하세요."
    )


def extract_wav(video_path: Path, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_path(), "-y", "-i", str(video_path),
        "-ac", "1", "-ar", "16000", "-vn",
        "-loglevel", "error",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return out_path
