import shutil
from pathlib import Path
import pytest
from mma_sub.db import repository
from mma_sub.core import glossary
from mma_sub.core.pipeline import process_video

VIDEO = Path(__file__).parent.parent / "fixtures" / "sample_speech.mp4"
GLOSS = Path(__file__).parent.parent / "fixtures" / "glossary.csv"

pytestmark = [
    pytest.mark.heavy,
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required"),
]


def test_end_to_end_produces_srt_and_mkv(tmp_path: Path):
    db = tmp_path / "p.sqlite3"
    repository.init_db(db)
    glossary.import_csv(db, GLOSS)
    out_dir = tmp_path / "out"

    progress_log: list[tuple[str, float]] = []
    def on_progress(stage: str, frac: float) -> None:
        progress_log.append((stage, frac))

    result = process_video(VIDEO, out_dir, db_path=db, progress=on_progress)

    assert result.srt_path.exists()
    assert result.mkv_path.exists()
    assert any(s == "stt" for s, _ in progress_log)
    assert any(s == "translating" for s, _ in progress_log)
    assert any(s == "muxing" for s, _ in progress_log)
    assert any(s == "done" for s, _ in progress_log)
    text = result.srt_path.read_text(encoding="utf-8")
    assert "가드 패스" in text
