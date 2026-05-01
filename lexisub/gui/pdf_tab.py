from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QFileDialog, QLabel, QProgressBar, QComboBox,
)
from loguru import logger
from lexisub.core import pdf_extractor
from lexisub.db import repository


class _ExtractWorker(QThread):
    progress = Signal(str, float)  # stage, frac
    one_done = Signal(int, int)    # pdf_index, terms_added
    failed = Signal(int, str)      # pdf_index, error
    all_done = Signal()

    def __init__(
        self,
        pdfs: list[Path],
        db_path: Path,
        source_lang: str,
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

        self.add_btn = QPushButton("PDF 추가")
        self.add_btn.setObjectName("add_pdf_button")
        self.add_btn.clicked.connect(self._on_add)

        self.refresh_btn = QPushButton("새로고침")
        self.refresh_btn.clicked.connect(self._refresh)

        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("source_lang_combo")
        self.lang_combo.addItems(["en", "pt", "ja", "es", "fr", "de"])
        self.lang_combo.setCurrentText("en")
        self.lang_combo.setToolTip("PDF 원본 언어")

        self.progress = QProgressBar()
        self.progress.setObjectName("pdf_progress")
        self.progress.setRange(0, 100)
        self.status = QLabel("대기 중")
        self.status.setObjectName("pdf_status_label")

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setObjectName("pdfs_table")
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("원본 언어:"))
        controls.addWidget(self.lang_combo)
        controls.addWidget(self.add_btn)
        controls.addWidget(self.refresh_btn)
        controls.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(self.table)

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

    def _on_add(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "PDF 선택 (다중 선택 가능)", "", "PDF (*.pdf)"
        )
        if not paths:
            return
        pdfs = [Path(p) for p in paths]
        self.add_btn.setEnabled(False)
        self.worker = _ExtractWorker(
            pdfs, self.db_path, source_lang=self.lang_combo.currentText()
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.one_done.connect(self._on_one_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.all_done.connect(self._on_all_done)
        self.worker.start()

    @Slot(str, float)
    def _on_progress(self, label: str, frac: float) -> None:
        self.progress.setValue(int(frac * 100))
        self.status.setText(label)
        self._refresh()  # so 'extracting' status shows

    @Slot(int, int)
    def _on_one_done(self, idx: int, n: int) -> None:
        self.status.setText(f"PDF {idx + 1} 완료: {n}개 용어 추출")
        self._refresh()

    @Slot(int, str)
    def _on_failed(self, idx: int, msg: str) -> None:
        self.status.setText(f"PDF {idx + 1} 실패: {msg}")
        self._refresh()

    @Slot()
    def _on_all_done(self) -> None:
        self.status.setText("모든 PDF 처리 완료. 용어집 탭에서 검토하세요.")
        self.add_btn.setEnabled(True)
        self.progress.setValue(100)
        self._refresh()
        if self.on_terms_changed:
            self.on_terms_changed()
