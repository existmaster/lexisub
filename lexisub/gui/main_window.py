from __future__ import annotations
from PySide6.QtWidgets import QMainWindow, QTabWidget
from lexisub.gui.video_tab import VideoTab
from lexisub.gui.glossary_tab import GlossaryTab
from lexisub.gui.pdf_tab import PdfTab
from lexisub import config
from lexisub.db import repository


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Lexisub")
        self.resize(1000, 650)
        repository.init_db(config.DB_PATH)
        tabs = QTabWidget()

        self.glossary_tab = GlossaryTab(config.DB_PATH)
        self.pdf_tab = PdfTab(
            config.DB_PATH,
            on_terms_changed=self.glossary_tab._refresh,
        )

        tabs.addTab(VideoTab(config.DB_PATH), "영상 처리")
        tabs.addTab(self.pdf_tab, "PDF 라이브러리")
        tabs.addTab(self.glossary_tab, "용어집")
        self.setCentralWidget(tabs)
