"""Тёмная тема окна: Fusion + QSS из набора токенов, как в Adalight."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#6c8cff"

BG = "#202225"
CARD = "#26282c"
INPUT = "#1b1d20"
BORDER = "#34373d"
HOVER = "#3d4148"
PRESSED = "#2a2c30"
TEXT = "#e4e4e7"
TEXT_DIM = "#9a9da3"
TITLE = "#9db1ff"

# Цвета индикаторов
OK = "#2ecc71"
WARN = "#e0a030"
BAD = "#e5534b"
IDLE = "#6a6d73"

BTN_START_QSS = (
    "QPushButton {background: #2e7d46; color: white; font-weight: 600;"
    " padding: 8px 14px; border: none; border-radius: 6px;}"
    "QPushButton:hover {background: #379554;}"
    "QPushButton:pressed {background: #27693b;}"
    f"QPushButton:disabled {{background: {HOVER}; color: {TEXT_DIM};}}"
)
BTN_STOP_QSS = (
    "QPushButton {background: #8b2e2e; color: white; font-weight: 600;"
    " padding: 8px 14px; border: none; border-radius: 6px;}"
    "QPushButton:hover {background: #a63a3a;}"
    "QPushButton:pressed {background: #772727;}"
    f"QPushButton:disabled {{background: {HOVER}; color: {TEXT_DIM};}}"
)

QSS = f"""
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ font-size: 13px; }}
QToolTip {{
    background: {CARD}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 6px; padding: 5px 8px;
}}

QGroupBox {{
    background: {CARD}; border: 1px solid {BORDER};
    border-radius: 10px; margin-top: 14px; padding: 12px 8px 8px 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 5px;
    color: {TITLE}; font-weight: 600;
}}

QPushButton {{
    background: {HOVER}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 6px 12px; min-height: 16px;
}}
QPushButton:hover {{ background: {BORDER}; }}
QPushButton:pressed {{ background: {PRESSED}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; background: transparent; }}

QComboBox, QSpinBox, QLineEdit {{
    background: {INPUT}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 4px 8px; min-height: 18px;
    selection-background-color: {ACCENT};
}}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 1px solid {BORDER};
    border-radius: 8px; selection-background-color: {HOVER};
}}
QSpinBox:disabled {{ color: {TEXT_DIM}; background: {BG}; }}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px; border: 1px solid {BORDER}; background: {INPUT};
}}
QCheckBox::indicator {{ border-radius: 4px; }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QRadioButton::indicator:checked {{
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 #ffffff, stop:0.35 #ffffff, stop:0.45 {ACCENT}, stop:1 {ACCENT});
    border-color: {ACCENT};
}}
QCheckBox:disabled, QRadioButton:disabled {{ color: {TEXT_DIM}; }}

QPlainTextEdit {{
    background: {INPUT}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 4px; selection-background-color: {ACCENT};
}}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ width: 10px; background: transparent; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {HOVER}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {BORDER}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QListWidget#sidebar {{ background: transparent; border: none; outline: none; }}
QListWidget#sidebar::item {{
    padding: 10px 12px; margin: 2px 4px; border-radius: 8px; color: {TEXT_DIM};
}}
QListWidget#sidebar::item:selected {{
    background: {HOVER}; color: {TEXT}; font-weight: 600;
}}
QListWidget#sidebar::item:hover:!selected {{ background: {CARD}; }}

QFrame#hero, QFrame#card {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;
}}
QLabel#heroState {{ font-size: 16px; font-weight: 700; background: transparent; }}
QLabel#heroSub {{ color: {TEXT_DIM}; background: transparent; }}
QLabel#heroDot {{ font-size: 20px; background: transparent; }}
QLabel#appTitle {{ font-size: 15px; font-weight: 700; padding: 6px 12px 0 12px; }}
QLabel#appVersion {{ color: {TEXT_DIM}; padding: 0 12px 6px 12px; }}
QLabel#dim {{ color: {TEXT_DIM}; background: transparent; }}
QLabel#statValue {{ font-size: 22px; font-weight: 700; background: transparent; }}
QLabel#preview {{
    background: {INPUT}; border: 1px solid {BORDER}; border-radius: 10px;
    color: {TEXT_DIM};
}}
QLabel#hintLabel {{
    background: {CARD}; color: {TEXT_DIM};
    border: 1px solid {BORDER}; border-radius: 8px; padding: 8px 10px;
}}
"""


def _dark_palette() -> QPalette:
    p = QPalette()
    window = QColor(BG)
    base = QColor(INPUT)
    text = QColor(TEXT)
    disabled = QColor(TEXT_DIM)

    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, window)
    p.setColor(QPalette.ColorRole.ToolTipBase, base)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, window)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 92, 92))
    p.setColor(QPalette.ColorRole.Link, QColor(ACCENT))
    p.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return p


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setPalette(_dark_palette())
    app.setStyleSheet(QSS)
    # Тёмный заголовок окна в Windows (Qt 6.8+)
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):
        hints.setColorScheme(Qt.ColorScheme.Dark)
