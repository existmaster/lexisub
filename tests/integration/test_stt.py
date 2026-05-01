import shutil
from pathlib import Path
import pytest
from mma_sub.core.audio import extract_wav
from mma_sub.core.stt import transcribe

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_speech.mp4"

pytestmark = [
    pytest.mark.heavy,
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required"),
]


def test_transcribe_returns_cues_with_recognizable_text(tmp_path: Path):
    wav = tmp_path / "speech.wav"
    extract_wav(FIXTURE, wav)
    cues, lang = transcribe(wav)
    assert len(cues) >= 1
    full = " ".join(c.text for c in cues).lower()
    assert "mma" in full or "training" in full or "guard" in full
    assert lang in {"en", "english"}
