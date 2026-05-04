from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from lexisub.gui.main_window import MainWindow
from lexisub.gui.styles import load_stylesheet


def _check_ffmpeg(parent=None) -> bool:
    """Verify a usable ffmpeg is available before opening the main window.

    The .app bundle ships imageio-ffmpeg's static binary, so this should
    succeed on every supported install. If somehow the bundle is broken
    or the user is running from source without the dependency, show a
    friendly Korean dialog instead of crashing later mid-pipeline.
    """
    from lexisub.core.audio import ffmpeg_path, FfmpegMissingError

    try:
        ffmpeg_path()
        return True
    except FfmpegMissingError:
        QMessageBox.critical(
            parent,
            "ffmpeg를 찾을 수 없습니다",
            "Lexisub 영상 처리에 ffmpeg가 필요합니다.\n\n"
            "정상 배포본에는 자동 포함되어 있습니다. "
            "소스에서 직접 실행 중이라면 터미널에서:\n\n"
            "    uv sync\n\n"
            "을 실행하거나, 시스템에 직접 설치하려면:\n\n"
            "    brew install ffmpeg\n\n"
            "을 실행하세요.",
        )
        return False


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Lexisub")
    app.setStyleSheet(load_stylesheet(app))
    if not _check_ffmpeg():
        return 1
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
