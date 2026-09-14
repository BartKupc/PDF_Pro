"""Pre-export flattened preview."""

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
    QVBoxLayout,
    QWidget,
)

from pdf_pro.export import ExportError, export_pdf


class PreviewDialog(QDialog):
    def __init__(self, source: Path, overlay, password: str | None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pre-export preview — flattened result")
        self.resize(720, 820)
        self.ok = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("This is the flattened export. Original file is not changed."))
        self.status = QLabel("Rendering preview…")
        layout.addWidget(self.status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        self.holder_layout = QVBoxLayout(holder)
        scroll.setWidget(holder)
        layout.addWidget(scroll)
        buttons = QHBoxLayout()
        export_btn = QPushButton("Looks good — choose export location")
        export_btn.clicked.connect(self._accept)
        cancel = QPushButton("Back")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(export_btn)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        self._build(source, overlay, password)

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

                        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
                        lab = QLabel()
                        lab.setPixmap(QPixmap.fromImage(img))
                        lab.setAlignment(Qt.AlignCenter)
                        self.holder_layout.addWidget(QLabel(f"Page {i + 1}"))
                        self.holder_layout.addWidget(lab)
                finally:
                    doc.close()
            self.status.setText("Preview of the flattened file.")
        except ExportError as exc:
            self.status.setText(f"Preview failed: {exc}")
        except Exception as exc:
            self.status.setText(f"Preview failed: {exc}")

    def _accept(self) -> None:
        self.ok = True
        self.accept()
