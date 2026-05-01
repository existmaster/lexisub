from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from pathlib import Path


class GlossaryTab(QWidget):
    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Glossary tab. (UI implemented in Task 15)"))
