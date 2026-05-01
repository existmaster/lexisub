import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QPushButton, QProgressBar, QLabel
from lexisub.gui.video_tab import VideoTab
from lexisub.db import repository


def test_video_tab_widgets_present(qtbot, tmp_path):
    db = tmp_path / "v.sqlite3"
    repository.init_db(db)
    w = VideoTab(db)
    qtbot.addWidget(w)
    assert w.findChild(QPushButton, "browse_button") is not None
    assert w.findChild(QPushButton, "start_button") is not None
    assert w.findChild(QProgressBar, "progress_bar") is not None
    assert w.findChild(QLabel, "status_label") is not None


def test_start_disabled_without_file(qtbot, tmp_path):
    db = tmp_path / "v.sqlite3"
    repository.init_db(db)
    w = VideoTab(db)
    qtbot.addWidget(w)
    start = w.findChild(QPushButton, "start_button")
    assert not start.isEnabled()
