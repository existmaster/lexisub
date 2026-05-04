from __future__ import annotations
from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTabWidget
from lexisub.gui.video_tab import VideoTab
from lexisub.gui.glossary_tab import GlossaryTab
from lexisub.gui.pdf_tab import PdfTab
from lexisub import config
from lexisub.db import repository


USER_GUIDE_URL = "https://github.com/existmaster/lexisub/blob/main/USER_GUIDE.ko.md"
ISSUES_URL = "https://github.com/existmaster/lexisub/issues"
RELEASES_URL = "https://github.com/existmaster/lexisub/releases/latest"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Lexisub")
        self.resize(1080, 720)
        self.setMinimumSize(880, 560)
        repository.init_db(config.DB_PATH)
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setMovable(False)

        self.glossary_tab = GlossaryTab(config.DB_PATH)
        self.pdf_tab = PdfTab(
            config.DB_PATH,
            on_terms_changed=self.glossary_tab._refresh,
        )

        tabs.addTab(VideoTab(config.DB_PATH), "영상 처리")
        tabs.addTab(self.pdf_tab, "PDF 라이브러리")
        tabs.addTab(self.glossary_tab, "용어집")
        self.setCentralWidget(tabs)

        self._build_menu()

    def _build_menu(self) -> None:
        bar = self.menuBar()
        help_menu = bar.addMenu("도움말")

        guide_action = QAction("사용 설명서", self)
        guide_action.setShortcut(QKeySequence("F1"))
        guide_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(USER_GUIDE_URL))
        )
        help_menu.addAction(guide_action)

        latest_action = QAction("최신 버전 확인", self)
        latest_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(RELEASES_URL))
        )
        help_menu.addAction(latest_action)

        issue_action = QAction("문제 신고", self)
        issue_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(ISSUES_URL))
        )
        help_menu.addAction(issue_action)

        help_menu.addSeparator()

        about_action = QAction("Lexisub 정보", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "Lexisub 정보",
            "<h3>Lexisub</h3>"
            "<p>영상에 한국어 자막을 자동으로 입혀주는 로컬 도구입니다. "
            "Apple Silicon Mac에서 인터넷 없이 동작합니다 "
            "(첫 실행 시 모델 다운로드 제외).</p>"
            "<p style='color:#666'>Apache License 2.0 · "
            "Whisper(MIT) + Gemma 모델은 Google Gemma Terms of Use 적용</p>"
            f"<p><a href='{USER_GUIDE_URL}'>사용 설명서</a> · "
            f"<a href='{RELEASES_URL}'>최신 버전</a></p>",
        )
