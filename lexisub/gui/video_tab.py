from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QProgressBar, QFileDialog, QMessageBox,
)
from loguru import logger
from lexisub.core.pipeline import process_video, PipelineResult


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


class VideoTab(QWidget):
    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        self.video_path: Path | None = None
        self.worker: _Worker | None = None
        self.setAcceptDrops(True)

        self.path_label = QLabel("영상 파일을 드래그하거나 [찾기]를 누르세요.")
        self.path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.path_label.setStyleSheet(
            "border: 2px dashed #888; padding: 30px; border-radius: 8px;"
        )

        self.browse_btn = QPushButton("찾기")
        self.browse_btn.setObjectName("browse_button")
        self.browse_btn.clicked.connect(self._on_browse)

        self.start_btn = QPushButton("자막 생성 시작")
        self.start_btn.setObjectName("start_button")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._on_start)

        self.progress = QProgressBar()
        self.progress.setObjectName("progress_bar")
        self.progress.setRange(0, 100)

        self.status = QLabel("대기 중")
        self.status.setObjectName("status_label")

        controls = QHBoxLayout()
        controls.addWidget(self.browse_btn)
        controls.addWidget(self.start_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.path_label)
        layout.addLayout(controls)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addStretch()

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent) -> None:
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
        self.path_label.setText(f"선택됨: {p.name}")
        self.start_btn.setEnabled(True)

    def _on_start(self) -> None:
        if not self.video_path:
            return
        self.start_btn.setEnabled(False)
        out_dir = self.video_path.parent
        self.worker = _Worker(self.video_path, out_dir, self.db_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    @Slot(str, float)
    def _on_progress(self, stage: str, frac: float) -> None:
        stages = {
            "extracting_audio": (0, 5, "음성 추출"),
            "stt": (5, 50, "음성 인식"),
            "translating": (50, 90, "번역"),
            "muxing": (90, 99, "자막 mux"),
            "done": (99, 100, "완료"),
        }
        lo, hi, label = stages.get(stage, (0, 100, stage))
        self.progress.setValue(int(lo + (hi - lo) * frac))
        self.status.setText(label)

    @Slot(object)
    def _on_done(self, result: PipelineResult) -> None:
        self.progress.setValue(100)
        self.status.setText(
            f"완료. SRT: {result.srt_path.name} / MKV: {result.mkv_path.name}"
        )
        self.start_btn.setEnabled(True)

    @Slot(str)
    def _on_failed(self, msg: str) -> None:
        self.status.setText(f"실패: {msg}")
        QMessageBox.critical(self, "처리 실패", msg)
        self.start_btn.setEnabled(True)
