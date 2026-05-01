from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from pathlib import Path


class VideoTab(QWidget):
    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Drop a video file here. (UI implemented in Task 14)"))
