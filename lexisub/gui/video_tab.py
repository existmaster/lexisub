from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, Slot, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QProgressBar, QFileDialog, QMessageBox, QFrame,
)
from loguru import logger
from lexisub.core.pipeline import process_video, PipelineResult
from lexisub.gui.subtitle_editor import SubtitleEditDialog


class _Worker(QThread):
    progress = Signal(str, float)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, video: Path, out_dir: Path, db_path: Path) -> None:
        super().__init__()
        self.video = video
        self.out_dir = out_dir
        self.db_path = db_path

    def run(self) -> None:
        try:
            res = process_video(
                self.video, self.out_dir, self.db_path,
                progress=lambda s, f: self.progress.emit(s, f),
            )
            self.finished_ok.emit(res)
        except Exception as e:
            logger.exception("pipeline failed")
            self.failed.emit(str(e))


_STAGES = [
    ("extracting_audio", "음성 추출", (0, 5)),
    ("stt", "음성 인식", (5, 50)),
    ("translating", "번역", (50, 90)),
    ("muxing", "자막 mux", (90, 99)),
    ("done", "완료", (99, 100)),
]
_STAGE_INDEX = {k: i for i, (k, _, _) in enumerate(_STAGES)}


class VideoTab(QWidget):
    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        self.video_path: Path | None = None
        self.last_result: PipelineResult | None = None
        self.worker: _Worker | None = None
        self.setAcceptDrops(True)

        # Heading
        heading = QLabel("영상 처리")
        heading.setProperty("role", "heading")
        subhead = QLabel("영상 파일을 드롭하거나 선택하면 한국어 자막이 자동으로 생성됩니다.")
        subhead.setProperty("role", "caption")

        # Drop zone
        self.drop_zone = QLabel("📁  영상 파일을 여기에 드롭하세요\n(.mp4 / .mov / .mkv / .m4v / .avi)")
        self.drop_zone.setObjectName("drop_zone")
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setMinimumHeight(140)

        # Selected file row
        self.selected_label = QLabel("")
        self.selected_label.setProperty("role", "caption")
        self.selected_label.setVisible(False)

        # Buttons
        self.browse_btn = QPushButton("파일 찾기")
        self.browse_btn.setObjectName("browse_button")
        self.browse_btn.clicked.connect(self._on_browse)

        self.start_btn = QPushButton("자막 생성 시작")
        self.start_btn.setObjectName("start_button")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._on_start)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.browse_btn)
        controls.addStretch()
        controls.addWidget(self.start_btn)

        # Stage indicator (label list)
        self.stage_labels: list[QLabel] = []
        stage_row = QHBoxLayout()
        stage_row.setSpacing(8)
        for k, label_text, _ in _STAGES:
            l = QLabel(label_text)
            l.setProperty("role", "caption")
            l.setStyleSheet("padding: 2px 8px;")
            self.stage_labels.append(l)
            stage_row.addWidget(l)
            if k != _STAGES[-1][0]:
                arrow = QLabel("→")
                arrow.setProperty("role", "caption")
                stage_row.addWidget(arrow)
        stage_row.addStretch()

        self.progress = QProgressBar()
        self.progress.setObjectName("progress_bar")
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)

        self.status = QLabel("대기 중")
        self.status.setObjectName("status_label")
        self.status.setVisible(False)

        # Result card (shown after completion)
        self.result_card = QFrame()
        self.result_card.setObjectName("card")
        result_layout = QVBoxLayout(self.result_card)
        result_layout.setSpacing(6)
        self.result_title = QLabel("✓  완료")
        self.result_title.setProperty("role", "heading")
        self.result_paths = QLabel("")
        self.result_paths.setProperty("role", "caption")
        self.result_paths.setWordWrap(True)
        self.edit_subs_btn = QPushButton("자막 편집")
        self.edit_subs_btn.setObjectName("edit_subs_button")
        self.edit_subs_btn.setToolTip(
            "한국어 자막을 줄별로 편집하고 .mkv를 재mux합니다. "
            "번역 누락(영어 그대로) / 음역 의심 줄을 자동 하이라이트합니다."
        )
        self.edit_subs_btn.clicked.connect(self._on_edit_subs)
        self.open_folder_btn = QPushButton("폴더 열기")
        self.open_folder_btn.clicked.connect(self._on_open_folder)
        result_btn_row = QHBoxLayout()
        result_btn_row.addWidget(self.edit_subs_btn)
        result_btn_row.addWidget(self.open_folder_btn)
        result_btn_row.addStretch()
        result_layout.addWidget(self.result_title)
        result_layout.addWidget(self.result_paths)
        result_layout.addLayout(result_btn_row)
        self.result_card.setVisible(False)

        # Main card containing the workflow
        main_card = QFrame()
        main_card.setObjectName("card")
        main_layout = QVBoxLayout(main_card)
        main_layout.setSpacing(14)
        main_layout.addWidget(heading)
        main_layout.addWidget(subhead)
        main_layout.addSpacing(4)
        main_layout.addWidget(self.drop_zone)
        main_layout.addWidget(self.selected_label)
        main_layout.addLayout(controls)
        main_layout.addLayout(stage_row)
        main_layout.addWidget(self.progress)
        main_layout.addWidget(self.status)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(16)
        outer.addWidget(main_card)
        outer.addWidget(self.result_card)
        outer.addStretch()

    # Drag-drop ----
    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            self.drop_zone.setProperty("active", "true")
            self.drop_zone.style().unpolish(self.drop_zone)
            self.drop_zone.style().polish(self.drop_zone)
            e.acceptProposedAction()

    def dragLeaveEvent(self, e) -> None:  # type: ignore[override]
        self.drop_zone.setProperty("active", "false")
        self.drop_zone.style().unpolish(self.drop_zone)
        self.drop_zone.style().polish(self.drop_zone)

    def dropEvent(self, e: QDropEvent) -> None:
        self.drop_zone.setProperty("active", "false")
        self.drop_zone.style().unpolish(self.drop_zone)
        self.drop_zone.style().polish(self.drop_zone)
        urls = e.mimeData().urls()
        if not urls:
            return
        self._set_video(Path(urls[0].toLocalFile()))

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "영상 선택", "", "Videos (*.mp4 *.mov *.mkv *.m4v *.avi)"
        )
        if path:
            self._set_video(Path(path))

    def _set_video(self, p: Path) -> None:
        self.video_path = p
        self.drop_zone.setText(f"📄  {p.name}")
        try:
            size_mb = p.stat().st_size / (1024 * 1024)
            self.selected_label.setText(f"{p}  ·  {size_mb:.1f} MB")
        except OSError:
            self.selected_label.setText(str(p))
        self.selected_label.setVisible(True)
        self.start_btn.setEnabled(True)
        self.result_card.setVisible(False)

    # Start ----
    def _on_start(self) -> None:
        if not self.video_path:
            return
        self.start_btn.setEnabled(False)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.status.setVisible(True)
        self.result_card.setVisible(False)
        self._set_active_stage(-1)
        out_dir = self.video_path.parent
        self.worker = _Worker(self.video_path, out_dir, self.db_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _set_active_stage(self, idx: int) -> None:
        for i, l in enumerate(self.stage_labels):
            if i < idx:
                l.setStyleSheet("padding: 2px 8px; color: #34c759; font-weight: 500;")
            elif i == idx:
                l.setStyleSheet("padding: 2px 8px; color: #007aff; font-weight: 600;")
            else:
                l.setStyleSheet("padding: 2px 8px;")

    @Slot(str, float)
    def _on_progress(self, stage: str, frac: float) -> None:
        idx = _STAGE_INDEX.get(stage, -1)
        self._set_active_stage(idx)
        if idx >= 0:
            _, label, (lo, hi) = _STAGES[idx]
            self.progress.setValue(int(lo + (hi - lo) * frac))
            self.status.setText(label)
        else:
            self.status.setText(stage)

    @Slot(object)
    def _on_done(self, result: PipelineResult) -> None:
        self.last_result = result
        self.progress.setValue(100)
        self._set_active_stage(len(self.stage_labels))
        self.status.setVisible(False)
        self.progress.setVisible(False)
        self.result_paths.setText(
            f"한국어 자막: {result.srt_path}\n자막 포함 영상: {result.mkv_path}"
        )
        self.result_card.setVisible(True)
        self.start_btn.setEnabled(True)

    @Slot(str)
    def _on_failed(self, msg: str) -> None:
        self.status.setText(f"실패: {msg}")
        self._set_active_stage(-1)
        QMessageBox.critical(self, "처리 실패", msg)
        self.start_btn.setEnabled(True)

    def _on_open_folder(self) -> None:
        if not self.last_result:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_result.mkv_path.parent)))

    def _on_edit_subs(self) -> None:
        if not self.last_result or not self.video_path:
            return
        dlg = SubtitleEditDialog(
            video_path=self.video_path,
            source_srt=self.last_result.source_srt_path,
            ko_srt=self.last_result.srt_path,
            mkv_out=self.last_result.mkv_path,
            parent=self,
        )
        dlg.exec()
