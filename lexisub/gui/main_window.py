from __future__ import annotations
from PySide6.QtWidgets import QMainWindow, QTabWidget
from lexisub.gui.video_tab import VideoTab
from lexisub.gui.glossary_tab import GlossaryTab
from lexisub import config
from lexisub.db import repository


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MMA Subtitle Tool")
        self.resize(900, 600)
        repository.init_db(config.DB_PATH)
        tabs = QTabWidget()
        tabs.addTab(VideoTab(config.DB_PATH), "영상 처리")
        tabs.addTab(GlossaryTab(config.DB_PATH), "용어집")
        self.setCentralWidget(tabs)
