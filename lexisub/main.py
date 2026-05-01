from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication
from lexisub.gui.main_window import MainWindow
from lexisub.gui.styles import load_stylesheet


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Lexisub")
    app.setStyleSheet(load_stylesheet(app))
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
