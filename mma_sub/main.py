from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication
from mma_sub.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
