from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox, QLabel,
)
from mma_sub.core import glossary
from mma_sub.db import repository


class GlossaryTab(QWidget):
    COLUMNS = ["언어", "원어 용어", "한국어 번역", "분류", "상태"]

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path

        self.import_btn = QPushButton("CSV 가져오기")
        self.import_btn.setObjectName("import_button")
        self.import_btn.clicked.connect(self._on_import)

        self.refresh_btn = QPushButton("새로고침")
        self.refresh_btn.clicked.connect(self._refresh)

        self.count_label = QLabel("")

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setObjectName("terms_table")
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self._on_toggle_status)

        controls = QHBoxLayout()
        controls.addWidget(self.import_btn)
        controls.addWidget(self.refresh_btn)
        controls.addWidget(self.count_label)
        controls.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.table)

        self._refresh()

    def _refresh(self) -> None:
        rows = repository.list_terms(self.db_path)
        self.table.setRowCount(len(rows))
        for r, term in enumerate(rows):
            cells = [
                term["source_lang"], term["source_term"],
                term["ko_term"], term["category"] or "",
                term["status"],
            ]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setData(Qt.ItemDataRole.UserRole, term["id"])
                self.table.setItem(r, c, item)
        self.count_label.setText(f"{len(rows)}개 용어")

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "용어집 CSV", "", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            n = glossary.import_csv(
                self.db_path, Path(path), default_status="approved"
            )
        except Exception as e:
            QMessageBox.critical(self, "가져오기 실패", str(e))
            return
        QMessageBox.information(self, "완료", f"{n}개 용어를 가져왔습니다.")
        self._refresh()

    def _on_toggle_status(self, item: QTableWidgetItem) -> None:
        term_id = item.data(Qt.ItemDataRole.UserRole)
        if term_id is None:
            return
        current = repository.get_term(self.db_path, term_id)
        if not current:
            return
        new_status = "pending" if current["status"] == "approved" else "approved"
        repository.set_term_status(self.db_path, term_id, new_status)
        self._refresh()
