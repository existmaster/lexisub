from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QFileDialog, QLabel, QProgressBar, QComboBox,
    QFrame, QStackedLayout, QHeaderView, QMessageBox, QAbstractItemView,
)
from loguru import logger
from lexisub.core import pdf_extractor
from lexisub.db import repository


class _ExtractWorker(QThread):
    progress = Signal(str, float)
    one_done = Signal(int, int)
    failed = Signal(int, str)
    all_done = Signal()

    def __init__(
        self,
        pdfs: list[Path],
        db_path: Path,
        source_lang: str | None,
    ) -> None:
        super().__init__()
        self.pdfs = pdfs
        self.db_path = db_path
        self.source_lang = source_lang

    def run(self) -> None:
        for i, p in enumerate(self.pdfs):
            try:
                n = pdf_extractor.extract_terms(
                    p,
                    self.db_path,
                    source_lang=self.source_lang,
                    progress=lambda s, f, idx=i: self.progress.emit(
                        f"PDF {idx + 1}/{len(self.pdfs)} {s}", f
                    ),
                )
                self.one_done.emit(i, n)
            except Exception as e:
                logger.exception(f"PDF extraction failed: {p}")
                self.failed.emit(i, str(e))
        self.all_done.emit()


class PdfTab(QWidget):
    COLUMNS = ["제목", "페이지", "언어", "상태", "경로"]

    def __init__(self, db_path: Path, on_terms_changed=None) -> None:
        super().__init__()
        self.db_path = db_path
        self.on_terms_changed = on_terms_changed
        self.worker: _ExtractWorker | None = None

        # Heading
        heading = QLabel("PDF 라이브러리")
        heading.setProperty("role", "heading")
        subhead = QLabel(
            "PDF를 추가하면 본문에서 도메인 용어가 자동 추출됩니다. "
            "추출된 용어는 [용어집] 탭에서 검토 후 영상 번역에 사용됩니다."
        )
        subhead.setProperty("role", "caption")
        subhead.setWordWrap(True)

        # Controls
        lang_label = QLabel("원본 언어")
        lang_label.setProperty("role", "caption")
        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("source_lang_combo")
        self.lang_combo.addItems(
            ["자동 감지", "en", "ko", "pt", "ja", "es", "fr", "de", "it", "ru", "zh-cn"]
        )
        self.lang_combo.setCurrentText("자동 감지")
        self.lang_combo.setToolTip(
            "PDF 원본 언어. '자동 감지'를 선택하면 PDF 텍스트로부터 자동으로 판단합니다."
        )
        self.lang_combo.setFixedWidth(140)

        self.add_btn = QPushButton("PDF 추가")
        self.add_btn.setObjectName("add_pdf_button")
        self.add_btn.clicked.connect(self._on_add)

        self.refresh_btn = QPushButton("새로고침")
        self.refresh_btn.clicked.connect(self._refresh)

        self.remove_btn = QPushButton("선택 제거")
        self.remove_btn.setObjectName("remove_pdf_button")
        self.remove_btn.clicked.connect(self._on_remove)
        self.remove_btn.setEnabled(False)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(lang_label)
        controls.addWidget(self.lang_combo)
        controls.addStretch()
        controls.addWidget(self.remove_btn)
        controls.addWidget(self.refresh_btn)
        controls.addWidget(self.add_btn)

        # Progress / status (visible only during extraction)
        self.progress = QProgressBar()
        self.progress.setObjectName("pdf_progress")
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        self.status = QLabel("")
        self.status.setObjectName("pdf_status_label")
        self.status.setVisible(False)

        # Table + empty state
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setObjectName("pdfs_table")
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        h = self.table.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self.empty_label = QLabel(
            "📚\n\n아직 추가된 PDF가 없습니다.\n[PDF 추가] 버튼으로 시작하세요."
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
        card_layout.addWidget(self.progress)
        card_layout.addWidget(self.status)
        card_layout.addWidget(stack_holder, stretch=1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.addWidget(card)

        self._refresh()

    def _refresh(self) -> None:
        rows = repository.list_pdfs(self.db_path)
        self.table.setRowCount(len(rows))
        for r, pdf in enumerate(rows):
            cells = [
                pdf["title"] or "—",
                str(pdf["page_count"] or "?"),
                pdf["language"] or "?",
                pdf["extraction_status"],
                pdf["path"],
            ]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setData(Qt.ItemDataRole.UserRole, pdf["id"])
                self.table.setItem(r, c, item)
        self.stack.setCurrentIndex(1 if rows else 0)

    def _on_add(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "PDF 선택 (다중 선택 가능)", "", "PDF (*.pdf)"
        )
        if not paths:
            return
        pdfs = [Path(p) for p in paths]
        self.add_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status.setVisible(True)
        choice = self.lang_combo.currentText()
        lang = None if choice == "자동 감지" else choice
        self.worker = _ExtractWorker(pdfs, self.db_path, source_lang=lang)
        self.worker.progress.connect(self._on_progress)
        self.worker.one_done.connect(self._on_one_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.all_done.connect(self._on_all_done)
        self.worker.start()

    @Slot(str, float)
    def _on_progress(self, label: str, frac: float) -> None:
        self.progress.setValue(int(frac * 100))
        self.status.setText(label)
        self._refresh()

    @Slot(int, int)
    def _on_one_done(self, idx: int, n: int) -> None:
        self.status.setText(f"PDF {idx + 1} 완료 — {n}개 용어 추출")
        self._refresh()

    @Slot(int, str)
    def _on_failed(self, idx: int, msg: str) -> None:
        self.status.setText(f"PDF {idx + 1} 실패: {msg}")
        self._refresh()

    @Slot()
    def _on_all_done(self) -> None:
        self.status.setText("✓  모든 PDF 처리 완료. [용어집] 탭에서 검토하세요.")
        self.add_btn.setEnabled(True)
        self.progress.setValue(100)
        self._refresh()
        if self.on_terms_changed:
            self.on_terms_changed()

    def _on_selection_changed(self) -> None:
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        self.remove_btn.setEnabled(bool(rows))

    def _selected_pdf_ids(self) -> list[int]:
        ids: list[int] = []
        for row in {idx.row() for idx in self.table.selectedIndexes()}:
            item = self.table.item(row, 0)
            if item is None:
                continue
            pdf_id = item.data(Qt.ItemDataRole.UserRole)
            if pdf_id is not None:
                ids.append(int(pdf_id))
        return ids

    def _on_remove(self) -> None:
        ids = self._selected_pdf_ids()
        if not ids:
            return
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("PDF 제거")
        msg.setText(f"{len(ids)}개 PDF를 라이브러리에서 제거합니다.")
        msg.setInformativeText(
            "PDF 파일 자체는 삭제하지 않습니다.\n"
            "이 PDF에서만 자동 추출된 보류(pending) 용어를 함께 정리할까요?"
        )
        prune_btn = msg.addButton("PDF 제거 + 보류 용어 정리", QMessageBox.ButtonRole.DestructiveRole)
        only_btn = msg.addButton("PDF만 제거", QMessageBox.ButtonRole.ActionRole)
        cancel_btn = msg.addButton("취소", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(only_btn)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked is cancel_btn or clicked is None:
            return
        for pdf_id in ids:
            repository.delete_pdf(self.db_path, pdf_id)
        if clicked is prune_btn:
            n = repository.prune_orphan_terms(self.db_path)
            self.status.setText(f"✓  {len(ids)}개 PDF 제거, {n}개 보류 용어 정리")
            self.status.setVisible(True)
        else:
            self.status.setText(f"✓  {len(ids)}개 PDF 제거")
            self.status.setVisible(True)
        self._refresh()
        if self.on_terms_changed:
            self.on_terms_changed()
