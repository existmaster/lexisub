import json
import shutil
import subprocess
from pathlib import Path
import pytest
from lexisub.core.muxer import mux_subtitle

VIDEO = Path(__file__).parent.parent / "fixtures" / "sample_30s.mp4"
SRT = Path(__file__).parent.parent / "fixtures" / "sample.srt"

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)


def test_mux_creates_mkv_with_subtitle_track(tmp_path: Path):
    out = tmp_path / "out.mkv"
    mux_subtitle(VIDEO, SRT, out, language="kor")
    assert out.exists()
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout
    streams = json.loads(info)["streams"]
    sub_streams = [s for s in streams if s["codec_type"] == "subtitle"]
    assert len(sub_streams) == 1
    assert sub_streams[0].get("tags", {}).get("language") == "kor"


def test_mux_does_not_reencode_video(tmp_path: Path):
    out = tmp_path / "out.mkv"
    mux_subtitle(VIDEO, SRT, out, language="kor")
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout
    streams = json.loads(info)["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    assert video["codec_name"] == "h264"
