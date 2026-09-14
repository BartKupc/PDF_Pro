"""Pre-export flattened preview. Footer buttons stay visible on short screens."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pdf_pro.export import ExportError, export_pdf


class PreviewDialog(QDialog):
    def __init__(self, source: Path, overlay, password: str | None, parent=None) -> None:
        super().__init__(parent)
        self.ok = False
        self._setup_ui()
        self._build(source, overlay, password)

    def _setup_ui(self) -> None:
        self.setWindowTitle("Pre-export preview — flattened result")
        self.setMinimumSize(560, 480)
        self.resize(700, 620)
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hint = QLabel("This is the flattened export. Original file is not changed.")
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.status = QLabel("Rendering preview…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        holder = QWidget()
        self.holder_layout = QVBoxLayout(holder)
        self.scroll.setWidget(holder)
        layout.addWidget(self.scroll, 1)

        self.footer = QWidget()
        buttons = QHBoxLayout(self.footer)
        buttons.setContentsMargins(0, 8, 0, 0)
        self.export_btn = QPushButton("Looks good — choose export location")
        self.export_btn.setObjectName("primaryAction")
        self.export_btn.setMinimumHeight(36)
        self.export_btn.clicked.connect(self._accept)
        cancel = QPushButton("Back")
        cancel.setMinimumHeight(36)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(self.export_btn, 1)
        buttons.addWidget(cancel)
        layout.addWidget(self.footer, 0)

    def _build(self, source, overlay, password) -> None:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "preview.pdf"
                export_pdf(source, overlay, dest, password=password)
                import fitz

                doc = fitz.open(dest.as_posix())
                try:
                    for i, page in enumerate(doc):
                        pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
                        from PySide6.QtGui import QImage

                        img = QImage(
                            pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888
                        ).copy()
                        lab = QLabel()
                        lab.setPixmap(QPixmap.fromImage(img))
                        lab.setAlignment(Qt.AlignCenter)
                        self.holder_layout.addWidget(QLabel(f"Page {i + 1}"))
                        self.holder_layout.addWidget(lab)
                finally:
                    doc.close()
            self.status.setText("Preview of the flattened file.")
            self.export_btn.setEnabled(True)
        except ExportError as exc:
            self.status.setText(f"Preview failed: {exc}")
            self.export_btn.setEnabled(False)
        except Exception as exc:
            self.status.setText(f"Preview failed: {exc}")
            self.export_btn.setEnabled(False)

    def _accept(self) -> None:
        self.ok = True
        self.accept()
