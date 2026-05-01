import shutil
import subprocess
from pathlib import Path
import pytest
from mma_sub.core.audio import extract_wav

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_30s.mp4"


pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


def test_extract_wav_creates_16khz_mono(tmp_path: Path):
    out = tmp_path / "audio.wav"
    extract_wav(FIXTURE, out)
    assert out.exists() and out.stat().st_size > 0
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=channels,sample_rate", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    sample_rate, channels = info.split(",")
    assert int(sample_rate) == 16000
    assert int(channels) == 1
