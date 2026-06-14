"""Tema visual moderno (escuro) da aplicação.

Centraliza a paleta de cores, a folha de estilo (QSS) e a configuração do
pyqtgraph para um visual coeso em toda a interface.
"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

# ---------------------------------------------------------------- Paleta
BG = "#0f1216"          # fundo da janela
SURFACE = "#181c22"     # cartões / painéis
SURFACE_2 = "#1f242c"   # campos / cabeçalhos
BORDER = "#2b313b"
TEXT = "#e6e8eb"
MUTED = "#9aa1ab"
ACCENT = "#E94A12"      # laranja (destaque/ações)
ACCENT_HOVER = "#ff5a22"
GREEN = "#2ecc71"
YELLOW = "#f2c14e"
RED = "#ff5d5d"
BLUE = "#4aa3ff"

# Cores de séries para os gráficos.
SERIES = ["#E94A12", "#4aa3ff", "#2ecc71", "#b07cff",
          "#f2c14e", "#16c6c6", "#ff7ac6", "#9aa1ab"]
BAND_COLOR = {"2.4 GHz": "#E94A12", "5 GHz": "#4aa3ff", "6 GHz": "#2ecc71"}


QSS = f"""
* {{
    font-family: -apple-system, "SF Pro Text", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QWidget {{ background: {BG}; }}

/* Abas */
QTabWidget::pane {{ border: none; background: {BG}; }}
QTabBar::tab {{
    background: transparent; color: {MUTED};
    padding: 9px 18px; margin-right: 4px;
    border: none; border-bottom: 2px solid transparent;
    font-weight: 600;
}}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

/* Botões */
QPushButton {{
    background: {SURFACE_2}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 8px;
    padding: 8px 14px; font-weight: 600;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:disabled {{ color: {MUTED}; border-color: {SURFACE_2}; }}
QPushButton#primary {{ background: {ACCENT}; border: none; color: white; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary:disabled {{ background: {SURFACE_2}; color: {MUTED}; }}

/* Campos */
QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {SURFACE_2}; border: 1px solid {BORDER};
    border-radius: 7px; padding: 5px 8px; min-height: 20px;
}}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT}; outline: none;
}}

/* Cartões / grupos */
QGroupBox, QFrame#card {{
    background: {SURFACE}; border: 1px solid {BORDER};
    border-radius: 12px; margin-top: 6px;
}}
QGroupBox {{ padding: 10px; }}
QLabel#cardTitle {{ color: {MUTED}; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1px; }}
QLabel#cardValue {{ color: {TEXT}; font-size: 26px; font-weight: 800; }}
QLabel#muted {{ color: {MUTED}; }}

/* Tabela */
QTableWidget {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
    gridline-color: {SURFACE_2}; alternate-background-color: {SURFACE_2};
    selection-background-color: {ACCENT};
}}
QHeaderView::section {{
    background: {SURFACE_2}; color: {MUTED}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 8px; font-weight: 700;
}}
QTableWidget::item {{ padding: 4px; border: none; }}

/* Progress */
QProgressBar {{
    background: {SURFACE_2}; border: none; border-radius: 6px;
    height: 10px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ border-radius: 6px; background: {ACCENT}; }}

/* Texto */
QPlainTextEdit {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
    padding: 12px; font-size: 14px; line-height: 1.5;
}}

/* Scrollbars */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QStatusBar {{ background: {BG}; color: {MUTED}; }}
QSplitter::handle {{ background: {BORDER}; }}
"""


def apply_theme(app: QApplication) -> None:
    """Aplica o tema escuro à aplicação e ao pyqtgraph."""
    app.setStyleSheet(QSS)
    pg.setConfigOptions(
        antialias=True, background=SURFACE, foreground=MUTED,
        imageAxisOrder="row-major",
    )
