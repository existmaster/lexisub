"""Smoke tests for the subtitle editor dialog."""

import pytest
pytest.importorskip("PySide6")

from pathlib import Path
from PySide6.QtWidgets import QTableWidget
from lexisub.core import subtitle
from lexisub.gui.subtitle_editor import SubtitleEditDialog, _classify


# ---- pure classification logic --------------------------------------

def test_classify_korean_normal():
    assert _classify("발꿈치 접지는 보행의 시작입니다.") == "ok"


def test_classify_fallback_english():
    assert _classify("Let's talk about the bottom player.") == "fallback"


def test_classify_mixed_korean_alpha():
    # "Tyl러" pattern — Korean+Alphabet without space
    assert _classify("Tyl러가 다리를 사용합니다.") == "mixed"


def test_classify_empty():
    assert _classify("") == "ok"
    assert _classify("   ") == "ok"


# ---- dialog smoke ---------------------------------------------------

def _write_srts(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a fake video, source SRT, and Korean SRT for the dialog."""
    src = tmp_path / "v.src.srt"
    ko = tmp_path / "v.ko.srt"
    video = tmp_path / "v.mp4"
    src.write_text(
        subtitle.serialize_srt([
            subtitle.Cue(1, 0, 2000, "Welcome to MMA training."),
            subtitle.Cue(2, 2000, 4000, "Today we cover guard pass."),
            subtitle.Cue(3, 4000, 6000, "And then we drill it."),
        ]),
        encoding="utf-8",
    )
    ko.write_text(
        subtitle.serialize_srt([
            subtitle.Cue(1, 0, 2000, "훈련에 오신 것을 환영합니다."),
            subtitle.Cue(2, 2000, 4000, "Today we cover guard pass."),  # fallback
            subtitle.Cue(3, 4000, 6000, "Tyl러가 그것을 연습합니다."),  # mixed
        ]),
        encoding="utf-8",
    )
    video.write_bytes(b"")  # placeholder; we won't re-mux in this test
    return video, src, ko


def test_dialog_opens_and_table_populated(qtbot, tmp_path):
    video, src, ko = _write_srts(tmp_path)
    mkv = tmp_path / "v.subbed.mkv"
    dlg = SubtitleEditDialog(video, src, ko, mkv)
    qtbot.addWidget(dlg)
    table = dlg.findChild(QTableWidget, "subtitle_edit_table")
    assert table is not None
    assert table.rowCount() == 3
    assert table.item(0, 2).text() == "Welcome to MMA training."
    assert table.item(0, 3).text() == "훈련에 오신 것을 환영합니다."


def test_save_srt_only_writes_back_changes(qtbot, tmp_path, monkeypatch):
    # Suppress modal QMessageBox so the test doesn't hang.
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: 0)

    video, src, ko = _write_srts(tmp_path)
    mkv = tmp_path / "v.subbed.mkv"
    dlg = SubtitleEditDialog(video, src, ko, mkv)
    qtbot.addWidget(dlg)
    table = dlg.findChild(QTableWidget, "subtitle_edit_table")
    table.item(1, 3).setText("오늘은 가드 패스를 다룹니다.")
    dlg._on_save_srt_only()
    saved = subtitle.parse_srt(ko.read_text(encoding="utf-8"))
    assert saved[1].text == "오늘은 가드 패스를 다룹니다."
    assert saved[0].start_ms == 0
    assert saved[2].end_ms == 6000


def test_filter_hides_ok_rows_when_only_susp_checked(qtbot, tmp_path):
    video, src, ko = _write_srts(tmp_path)
    mkv = tmp_path / "v.subbed.mkv"
    dlg = SubtitleEditDialog(video, src, ko, mkv)
    qtbot.addWidget(dlg)
    table = dlg.findChild(QTableWidget, "subtitle_edit_table")
    # Row 0 is normal Korean → 'ok'; rows 1 & 2 are fallback / mixed.
    dlg.only_susp.setChecked(True)
    assert table.isRowHidden(0)
    assert not table.isRowHidden(1)
    assert not table.isRowHidden(2)
