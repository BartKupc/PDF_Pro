"""Mission-control dark theme. One module — apply at app start.

Palette is locked: near-black surfaces, white primary text, muted grey
secondary, electric blue accent on primary actions and selection only.
"""

from __future__ import annotations

# Near-black range #0a0a0f–#12121a
BG = "#0a0a0f"
SURFACE = "#12121a"
SURFACE_2 = "#181822"
TEXT = "#ffffff"
MUTED = "#9ca3af"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#2563eb"
ACCENT_PRESSED = "#1d4ed8"
BORDER = "#2a2a36"
DANGER = "#f87171"
WARNING_BG = "#2a2110"
WARNING_FG = "#fbbf24"
LEGAL_BG = "#1a1610"
LEGAL_FG = "#e5c07b"

QSS = f"""
* {{
    font-size: 13px;
}}
QWidget {{
    background-color: {BG};
    color: {TEXT};
    border: none;
}}
QMainWindow, QDialog, QMenuBar, QMenu {{
    background-color: {BG};
    color: {TEXT};
}}
QMenu {{
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 8px 16px;
}}
QMenu::item:selected {{
    background-color: {ACCENT};
    color: {TEXT};
}}
QToolBar {{
    background-color: {SURFACE};
    border: none;
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 8px 10px;
}}
QToolBar QToolButton {{
    background-color: transparent;
    color: {TEXT};
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 36px;
}}
QToolBar QToolButton:hover {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
}}
QToolBar QToolButton:pressed {{
    background-color: {BORDER};
}}
QToolBar QToolButton:disabled {{
    color: {MUTED};
}}
QPushButton {{
    background-color: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 8px 14px;
    min-height: 36px;
}}
QPushButton:hover {{
    background-color: {SURFACE};
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: {BORDER};
}}
QPushButton:disabled {{
    color: {MUTED};
    background-color: {SURFACE};
}}
QPushButton#primaryAction {{
    background-color: {ACCENT};
    color: {TEXT};
    border: 1px solid {ACCENT};
    font-weight: 600;
}}
QPushButton#primaryAction:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton#primaryAction:pressed {{
    background-color: {ACCENT_PRESSED};
}}
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 8px;
    min-height: 36px;
    selection-background-color: {ACCENT};
    selection-color: {TEXT};
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
}}
QListWidget {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    outline: none;
}}
QListWidget::item {{
    padding: 8px;
}}
QListWidget::item:selected {{
    background-color: {ACCENT};
    color: {TEXT};
}}
QListWidget::item:hover {{
    background-color: {SURFACE_2};
}}
QTabWidget::pane {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
}}
QTabBar::tab {{
    background-color: {BG};
    color: {MUTED};
    border: 1px solid {BORDER};
    padding: 8px 16px;
    min-height: 28px;
}}
QTabBar::tab:selected {{
    background-color: {SURFACE};
    color: {TEXT};
    border-bottom: 1px solid {ACCENT};
}}
QTabBar::tab:hover {{
    color: {TEXT};
}}
QTabWidget#ribbon {{
    background-color: {SURFACE};
    max-height: 110px;
    min-height: 90px;
}}
QTabWidget#ribbon::pane {{
    background-color: {SURFACE};
    border: none;
    border-bottom: 1px solid {BORDER};
}}
QTabWidget#ribbon QTabBar::tab {{
    background-color: {BG};
    color: {MUTED};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 6px 14px;
    min-height: 24px;
    font-size: 12px;
}}
QTabWidget#ribbon QTabBar::tab:selected {{
    background-color: {SURFACE};
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
}}
QFrame#ribbonGroup {{
    background-color: transparent;
    border: none;
}}
QLabel#ribbonGroupLabel {{
    color: {MUTED};
    font-size: 10px;
    padding: 0;
}}
QFrame#ribbonSeparator {{
    background-color: {BORDER};
    max-width: 1px;
}}
QTabWidget#ribbon QToolButton {{
    background-color: transparent;
    color: {TEXT};
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 32px;
    font-size: 12px;
}}
QTabWidget#ribbon QToolButton:hover {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
}}
QTabWidget#ribbon QToolButton:pressed {{
    background-color: {BORDER};
}}
QTabWidget#ribbon QToolButton:disabled {{
    color: {MUTED};
}}
QTabWidget#ribbon QPushButton {{
    min-height: 32px;
    padding: 4px 10px;
    font-size: 12px;
}}
QTabWidget#ribbon QComboBox, QTabWidget#ribbon QSpinBox {{
    min-height: 32px;
    padding: 2px 6px;
    font-size: 12px;
}}
QWidget#ribbonPage {{
    background-color: {SURFACE};
}}
QScrollArea, QAbstractScrollArea {{
    background-color: {BG};
    border: none;
}}
QScrollBar:vertical, QScrollBar:horizontal {{
    background: {SURFACE};
    border: none;
    width: 10px;
    height: 10px;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QSplitter::handle {{
    background-color: {BORDER};
}}
QStatusBar {{
    background-color: {SURFACE};
    color: {MUTED};
    border-top: 1px solid {BORDER};
}}
QLabel {{
    background-color: transparent;
    color: {TEXT};
}}
QLabel#mutedLabel {{
    color: {MUTED};
}}
QLabel#warningBanner {{
    background-color: {WARNING_BG};
    color: {WARNING_FG};
    padding: 8px 10px;
}}
QLabel#legalNotice {{
    background-color: {LEGAL_BG};
    color: {LEGAL_FG};
    padding: 8px 10px;
}}
QLabel#feedbackLabel {{
    color: {DANGER};
    padding: 4px 0;
}}
QLabel#feedbackOk {{
    color: {TEXT};
    padding: 4px 0;
}}
QCheckBox {{
    color: {TEXT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    background: {SURFACE};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QGraphicsView {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
}}
QMessageBox {{
    background-color: {SURFACE};
}}
QInputDialog {{
    background-color: {SURFACE};
}}
QProgressBar {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 3px;
    text-align: center;
    color: {TEXT};
    min-height: 12px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
}}
QTabWidget#docTabs::pane {{
    background-color: {SURFACE};
    border: none;
}}
QHeaderView::section {{
    background-color: {SURFACE};
    color: {MUTED};
    border: none;
    padding: 6px;
}}
"""


def apply_theme(app) -> None:
    """Apply Fusion + palette + QSS. Safe to call once after QApplication()."""
    from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
    from PySide6.QtWidgets import QStyleFactory

    if "Fusion" in QStyleFactory.keys():
        app.setStyle("Fusion")

    pal = QPalette()
    bg = QColor(BG)
    surface = QColor(SURFACE)
    text = QColor(TEXT)
    muted = QColor(MUTED)
    accent = QColor(ACCENT)
    pal.setColor(QPalette.Window, bg)
    pal.setColor(QPalette.WindowText, text)
    pal.setColor(QPalette.Base, surface)
    pal.setColor(QPalette.AlternateBase, QColor(SURFACE_2))
    pal.setColor(QPalette.Text, text)
    pal.setColor(QPalette.Button, surface)
    pal.setColor(QPalette.ButtonText, text)
    pal.setColor(QPalette.BrightText, text)
    pal.setColor(QPalette.ToolTipBase, surface)
    pal.setColor(QPalette.ToolTipText, text)
    pal.setColor(QPalette.Highlight, accent)
    pal.setColor(QPalette.HighlightedText, text)
    pal.setColor(QPalette.PlaceholderText, muted)
    pal.setColor(QPalette.Disabled, QPalette.Text, muted)
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, muted)
    pal.setColor(QPalette.Disabled, QPalette.WindowText, muted)
    app.setPalette(pal)

    db = QFontDatabase()
    families = set(db.families())
    for name in ("Inter", "Noto Sans", "DejaVu Sans"):
        if name in families:
            font = QFont(name, 13)
            app.setFont(font)
            break
    app.setStyleSheet(QSS)
