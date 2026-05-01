from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox, QLabel, QFrame,
    QStackedLayout, QHeaderView, QAbstractItemView,
)
from lexisub.core import glossary
from lexisub.db import repository


class GlossaryTab(QWidget):
    COLUMNS = ["언어", "원어 용어", "한국어 번역", "분류", "상태", "출처"]

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path

        # Heading
        heading = QLabel("용어집")
        heading.setProperty("role", "heading")
        subhead = QLabel(
            "더블클릭으로 승인 ↔ 보류를 토글하세요. 승인된 용어만 영상 번역에 적용됩니다."
        )
        subhead.setProperty("role", "caption")
        subhead.setWordWrap(True)

        # Top controls
        self.count_label = QLabel("0개")
        self.count_label.setProperty("role", "caption")

        self.refresh_btn = QPushButton("새로고침")
        self.refresh_btn.clicked.connect(self._refresh)

        self.import_btn = QPushButton("CSV 가져오기")
        self.import_btn.setObjectName("import_button")
        self.import_btn.clicked.connect(self._on_import)

        self.delete_btn = QPushButton("선택 삭제")
        self.delete_btn.setObjectName("delete_terms_button")
        self.delete_btn.clicked.connect(self._on_delete_selected)
        self.delete_btn.setEnabled(False)

        self.prune_btn = QPushButton("출처 없는 보류 정리")
        self.prune_btn.setObjectName("prune_orphans_button")
        self.prune_btn.setToolTip(
            "PDF가 모두 제거되어 출처가 사라진 보류(pending) 용어를 일괄 정리합니다.\n"
            "CSV로 가져온 승인된 용어는 영향 없습니다."
        )
        self.prune_btn.clicked.connect(self._on_prune_orphans)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.count_label)
        controls.addStretch()
        controls.addWidget(self.delete_btn)
        controls.addWidget(self.prune_btn)
        controls.addWidget(self.refresh_btn)
        controls.addWidget(self.import_btn)

        # Table
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setObjectName("terms_table")
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._on_toggle_status)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        # Delete key shortcut on the table
        self._del_shortcut = QShortcut(QKeySequence("Delete"), self.table)
        self._del_shortcut.activated.connect(self._on_delete_selected)
        self._backspace_shortcut = QShortcut(QKeySequence("Backspace"), self.table)
        self._backspace_shortcut.activated.connect(self._on_delete_selected)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setStretchLastSection(True)

        # Empty state
        self.empty_label = QLabel(
            "📖\n\n등록된 용어가 없습니다.\n"
            "[PDF 라이브러리]에서 PDF를 추가하거나 [CSV 가져오기]를 사용하세요."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setProperty("role", "caption")
        self.empty_label.setStyleSheet("padding: 48px;")

        self.stack = QStackedLayout()
        self.stack.addWidget(self.empty_label)
        self.stack.addWidget(self.table)
        stack_holder = QWidget()
        stack_holder.setLayout(self.stack)

        # Card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)
        card_layout.addWidget(heading)
        card_layout.addWidget(subhead)
        card_layout.addLayout(controls)
        card_layout.addWidget(stack_holder, stretch=1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.addWidget(card)

        self._refresh()

    def _refresh(self) -> None:
        rows = repository.list_terms(self.db_path)
        self.table.setRowCount(len(rows))
        for r, term in enumerate(rows):
            sources = repository.list_sources_for_term(self.db_path, term["id"])
            src_label = ", ".join(
                f"{s['pdf_title'] or Path(s['pdf_path']).name}:p{s['page_no']}"
                for s in sources
            ) if sources else "—"
            cells = [
                term["source_lang"], term["source_term"],
                term["ko_term"], term["category"] or "",
                term["status"], src_label,
            ]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setData(Qt.ItemDataRole.UserRole, term["id"])
                self.table.setItem(r, c, item)
        approved = sum(1 for r in rows if r["status"] == "approved")
        pending = len(rows) - approved
        self.count_label.setText(
            f"총 {len(rows)}개  ·  승인 {approved}개  ·  보류 {pending}개"
        )
        self.stack.setCurrentIndex(1 if rows else 0)

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

    def _on_selection_changed(self) -> None:
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        self.delete_btn.setEnabled(bool(rows))

    def _selected_term_ids(self) -> list[int]:
        ids: list[int] = []
        for row in {idx.row() for idx in self.table.selectedIndexes()}:
            item = self.table.item(row, 0)
            if item is None:
                continue
            term_id = item.data(Qt.ItemDataRole.UserRole)
            if term_id is not None:
                ids.append(int(term_id))
        return ids

    def _on_delete_selected(self) -> None:
        ids = self._selected_term_ids()
        if not ids:
            return
        ans = QMessageBox.question(
            self,
            "용어 삭제",
            f"{len(ids)}개 용어를 삭제합니다. 취소할 수 없습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        n = repository.delete_terms(self.db_path, ids)
        self._refresh()
        QMessageBox.information(self, "완료", f"{n}개 용어를 삭제했습니다.")

    def _on_prune_orphans(self) -> None:
        ans = QMessageBox.question(
            self,
            "출처 없는 보류 용어 정리",
            "PDF가 모두 제거되어 출처가 사라진 보류(pending) 상태의 용어를 일괄 삭제합니다.\n"
            "CSV로 가져온 승인된 용어는 영향이 없습니다. 진행할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        n = repository.prune_orphan_terms(self.db_path)
        self._refresh()
        QMessageBox.information(self, "완료", f"{n}개 보류 용어를 정리했습니다.")
