"""Global Qt stylesheet for Lexisub.

Light/dark adaptive. Uses macOS-native font families and the system
accent palette where possible. Loaded once in main.py via
``app.setStyleSheet(load_stylesheet())``.
"""

from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication


# Spacing scale (px)
SP_XS = 4
SP_SM = 8
SP_MD = 12
SP_LG = 16
SP_XL = 24


def _is_dark(app: QApplication) -> bool:
    bg = app.palette().color(QPalette.ColorRole.Window)
    # Brightness: Y = 0.299R + 0.587G + 0.114B
    y = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
    return y < 128


def load_stylesheet(app: QApplication | None = None) -> str:
    app = app or QApplication.instance()  # type: ignore[assignment]
    dark = _is_dark(app) if app else False

    if dark:
        bg_card = "#252527"
        bg_card_hover = "#2d2d30"
        bg_input = "#1e1e20"
        border = "#3a3a3d"
        border_strong = "#48484c"
        text_primary = "#f2f2f7"
        text_secondary = "#a1a1a6"
        text_tertiary = "#6c6c70"
        accent = "#0a84ff"
        accent_hover = "#3597ff"
        accent_text = "#ffffff"
        zebra = "#2a2a2d"
    else:
        bg_card = "#ffffff"
        bg_card_hover = "#f6f6f8"
        bg_input = "#f2f2f4"
        border = "#e3e3e6"
        border_strong = "#c7c7cc"
        text_primary = "#1c1c1e"
        text_secondary = "#48484a"
        text_tertiary = "#8e8e93"
        accent = "#007aff"
        accent_hover = "#0a84ff"
        accent_text = "#ffffff"
        zebra = "#fafafa"

    return f"""
QWidget {{
    font-family: -apple-system, "SF Pro Text", "Pretendard",
                 "Apple SD Gothic Neo", sans-serif;
    font-size: 13px;
    color: {text_primary};
}}

QMainWindow {{
    background-color: {bg_input};
}}

/* Tab bar */
QTabWidget::pane {{
    border: none;
    background: {bg_input};
    top: -1px;
}}
QTabBar::tab {{
    padding: {SP_SM}px {SP_LG}px;
    margin-right: {SP_XS}px;
    background: transparent;
    border: none;
    color: {text_secondary};
    font-size: 13px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    color: {text_primary};
    border-bottom: 2px solid {accent};
}}
QTabBar::tab:hover:!selected {{
    color: {text_primary};
}}

/* Cards / sections */
QFrame#card {{
    background-color: {bg_card};
    border: 1px solid {border};
    border-radius: 10px;
    padding: {SP_LG}px;
}}

/* Drop zone */
QLabel#drop_zone {{
    background-color: {bg_card};
    border: 2px dashed {border_strong};
    border-radius: 12px;
    padding: 36px 24px;
    color: {text_secondary};
    font-size: 14px;
    qproperty-alignment: AlignCenter;
}}
QLabel#drop_zone[active="true"] {{
    border-color: {accent};
    background-color: {bg_card_hover};
    color: {text_primary};
}}

/* Headings & captions */
QLabel[role="heading"] {{
    font-size: 16px;
    font-weight: 600;
    color: {text_primary};
}}
QLabel[role="caption"] {{
    color: {text_tertiary};
    font-size: 12px;
}}

/* Status label */
QLabel#status_label, QLabel#pdf_status_label {{
    color: {text_secondary};
    font-size: 12px;
    padding: {SP_XS}px 0;
}}

/* Buttons */
QPushButton {{
    background-color: {bg_card};
    color: {text_primary};
    border: 1px solid {border_strong};
    border-radius: 6px;
    padding: 6px 14px;
    min-height: 24px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {bg_card_hover};
}}
QPushButton:pressed {{
    background-color: {border};
}}
QPushButton:disabled {{
    color: {text_tertiary};
    background-color: {bg_input};
    border-color: {border};
}}

/* Primary action (Start / Add PDF) */
QPushButton#start_button, QPushButton#add_pdf_button, QPushButton#import_button {{
    background-color: {accent};
    color: {accent_text};
    border: 1px solid {accent};
}}
QPushButton#start_button:hover,
QPushButton#add_pdf_button:hover,
QPushButton#import_button:hover {{
    background-color: {accent_hover};
}}
QPushButton#start_button:disabled,
QPushButton#add_pdf_button:disabled {{
    background-color: {bg_input};
    color: {text_tertiary};
    border-color: {border};
}}

/* Progress bar */
QProgressBar {{
    background-color: {bg_input};
    border: 1px solid {border};
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 4px;
}}

/* Tables */
QTableWidget {{
    background-color: {bg_card};
    alternate-background-color: {zebra};
    gridline-color: {border};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {accent};
    selection-color: {accent_text};
}}
QTableWidget::item {{
    padding: {SP_SM}px {SP_MD}px;
    border: none;
}}
QHeaderView {{
    background-color: {bg_input};
}}
QHeaderView::section {{
    background-color: {bg_input};
    color: {text_secondary};
    padding: {SP_SM}px {SP_MD}px;
    border: none;
    border-bottom: 1px solid {border};
    border-right: 1px solid {border};
    font-weight: 600;
    font-size: 12px;
}}
QHeaderView::section:last {{
    border-right: none;
}}

/* Combobox */
QComboBox {{
    background-color: {bg_card};
    color: {text_primary};
    border: 1px solid {border_strong};
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 22px;
}}
QComboBox:hover {{
    background-color: {bg_card_hover};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background-color: {bg_card};
    border: 1px solid {border_strong};
    selection-background-color: {accent};
    selection-color: {accent_text};
    padding: {SP_XS}px;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {border_strong};
    border-radius: 5px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {text_tertiary};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {border_strong};
    border-radius: 5px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {text_tertiary};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""
