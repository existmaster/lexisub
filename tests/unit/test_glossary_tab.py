import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QPushButton, QTableWidget
from mma_sub.gui.glossary_tab import GlossaryTab
from mma_sub.db import repository
from mma_sub.core import glossary
from pathlib import Path

FIXTURE = Path(__file__).parent.parent / "fixtures" / "glossary.csv"


def test_glossary_tab_has_widgets(qtbot, tmp_path):
    db = tmp_path / "g.sqlite3"
    repository.init_db(db)
    w = GlossaryTab(db)
    qtbot.addWidget(w)
    assert w.findChild(QPushButton, "import_button") is not None
    assert w.findChild(QTableWidget, "terms_table") is not None


def test_table_reflects_imported_terms(qtbot, tmp_path):
    db = tmp_path / "g.sqlite3"
    repository.init_db(db)
    glossary.import_csv(db, FIXTURE, default_status="approved")
    w = GlossaryTab(db)
    qtbot.addWidget(w)
    table = w.findChild(QTableWidget, "terms_table")
    assert table.rowCount() == 4
