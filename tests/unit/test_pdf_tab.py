import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QPushButton, QTableWidget, QComboBox
from lexisub.gui.pdf_tab import PdfTab
from lexisub.db import repository


def test_pdf_tab_widgets_present(qtbot, tmp_path):
    db = tmp_path / "p.sqlite3"
    repository.init_db(db)
    w = PdfTab(db)
    qtbot.addWidget(w)
    assert w.findChild(QPushButton, "add_pdf_button") is not None
    assert w.findChild(QTableWidget, "pdfs_table") is not None
    assert w.findChild(QComboBox, "source_lang_combo") is not None
