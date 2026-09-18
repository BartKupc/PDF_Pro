"""Microsoft-style ribbon: tabbed groups of actions. Dark theme via theme.py."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pdf_pro.ribbon_spec import (
    ACTIONS,
    TAB_ORDER,
    WIDGET_ACTIONS,
    action_ids_in_group,
    groups_for,
)

RIBBON_MIN_H = 90
RIBBON_MAX_H = 110


class RibbonGroup(QFrame):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ribbonGroup")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(2)
        self.row = QHBoxLayout()
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(4)
        layout.addLayout(self.row, 1)
        label = QLabel(title)
        label.setObjectName("ribbonGroupLabel")
        label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(label)


class RibbonBar(QTabWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ribbon")
        self.setDocumentMode(True)
        self.setMovable(False)
        self.setElideMode(Qt.ElideNone)
        self.setMinimumHeight(RIBBON_MIN_H)
        self.setMaximumHeight(RIBBON_MAX_H)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.widgets: dict[str, QWidget] = {}

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        height = min(RIBBON_MAX_H, max(RIBBON_MIN_H, hint.height()))
        return QSize(min(hint.width(), 1366), height)

    def populate(self, actions: dict, extras: dict) -> None:
        self.clear()
        self.widgets = {}
        spec = actions or ACTIONS
        for tab in TAB_ORDER:
            page = QWidget()
            page.setObjectName("ribbonPage")
            row = QHBoxLayout(page)
            row.setContentsMargins(8, 4, 8, 4)
            row.setSpacing(8)
            groups = groups_for(tab)
            for i, group in enumerate(groups):
                if i:
                    sep = QFrame()
                    sep.setObjectName("ribbonSeparator")
                    sep.setFrameShape(QFrame.VLine)
                    sep.setFixedWidth(1)
                    row.addWidget(sep)
                frame = RibbonGroup(group)
                for aid in action_ids_in_group(tab, group):
                    _tab, _g, label = spec[aid]
                    if aid in extras:
                        widget = extras[aid]
                    elif aid in WIDGET_ACTIONS:
                        widget = QLabel(label)
                    elif aid == "preview_export":
                        widget = QPushButton(label)
                        widget.setObjectName("primaryAction")
                        widget.setMinimumHeight(36)
                        widget.setMinimumWidth(160)
                    else:
                        widget = QToolButton()
                        widget.setText(label)
                        widget.setToolButtonStyle(Qt.ToolButtonTextOnly)
                        widget.setMinimumHeight(32)
                        widget.setAutoRaise(True)
                    self.widgets[aid] = widget
                    frame.row.addWidget(widget, 0, Qt.AlignVCenter)
                row.addWidget(frame, 0)
            row.addStretch(1)
            self.addTab(page, tab)
