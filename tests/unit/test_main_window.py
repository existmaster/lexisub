import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QTabWidget
from lexisub.gui.main_window import MainWindow


def test_main_window_has_two_tabs(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    tabs = w.findChild(QTabWidget)
    assert tabs is not None
    titles = [tabs.tabText(i) for i in range(tabs.count())]
    assert "영상 처리" in titles
    assert "용어집" in titles
