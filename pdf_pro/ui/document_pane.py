"""One open PDF: thumbnails + canvas bound to a DocumentSession."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QSplitter, QWidget

from pdf_pro.session import DocumentSession
from pdf_pro.ui.canvas import PageCanvas


class DocumentPane(QWidget):
    thumb_chosen = Signal(int)

    def __init__(self, session: DocumentSession, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.canvas = PageCanvas(self)
        self.canvas.bind_overlay(session.overlay)
        self.canvas.page_index = session.current_page
        self.canvas.zoom = session.zoom
        self.thumbs = QListWidget(self)
        self.thumbs.setMaximumWidth(160)
        self.thumbs.setIconSize(QSize(120, 160))
        self.thumbs.currentRowChanged.connect(self.thumb_chosen.emit)
        split = QSplitter(self)
        split.addWidget(self.thumbs)
        split.addWidget(self.canvas)
        split.setStretchFactor(1, 1)
        from PySide6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(split)

    def title(self) -> str:
        opened = self.session.opened
        name = opened.path.name if opened is not None else "Untitled"
        return name + (" *" if self.session.dirty else "")

    def fill_thumbs(self, count: int) -> None:
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        for i in range(count):
            self.thumbs.addItem(QListWidgetItem(f"{i + 1}"))
        self.thumbs.blockSignals(False)
