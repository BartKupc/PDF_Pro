"""Pre-export flattened preview. Pages render off the UI thread."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QEventLoop, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pdf_pro.ui.workers import PreviewWorker


class PreviewDialog(QDialog):
    def __init__(self, source: Path, overlay, password: str | None, parent=None, plan=None) -> None:
        super().__init__(parent)
        self.ok = False
        self._ready = False
        self._setup_ui()
        self._worker = PreviewWorker(source, overlay, password, plan=plan, parent=self)
        self._worker.page_ready.connect(self._add_page)
        self._worker.progress.connect(self._on_progress)
        self._worker.failed.connect(self._on_fail)
        self._worker.finished_ok.connect(self._on_ok)
        self._worker.start()

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

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)

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
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._accept)
        cancel = QPushButton("Back")
        cancel.setMinimumHeight(36)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(self.export_btn, 1)
        buttons.addWidget(cancel)
        layout.addWidget(self.footer, 0)

    def _add_page(self, index: int, image) -> None:
        lab = QLabel()
        lab.setPixmap(QPixmap.fromImage(image))
        lab.setAlignment(Qt.AlignCenter)
        self.holder_layout.addWidget(QLabel(f"Page {index + 1}"))
        self.holder_layout.addWidget(lab)

    def _on_progress(self, pct: int, msg: str) -> None:
        self.bar.setValue(pct)
        self.status.setText(msg)

    def _on_fail(self, msg: str) -> None:
        self.status.setText(f"Preview failed: {msg}")
        self.export_btn.setEnabled(False)
        self._ready = True

    def _on_ok(self) -> None:
        self.status.setText("Preview of the flattened file.")
        self.bar.setValue(100)
        self.export_btn.setEnabled(True)
        self._ready = True

    def wait_ready(self, timeout_ms: int = 60000) -> None:
        if self._ready:
            return
        loop = QEventLoop(self)
        self._worker.finished.connect(loop.quit)
        self._worker.failed.connect(lambda *_: loop.quit())
        self._worker.finished_ok.connect(lambda *_: loop.quit())
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()

    def _accept(self) -> None:
        self.ok = True
        self.accept()

    def closeEvent(self, event) -> None:
        if self._worker.isRunning():
            self._worker.wait(4000)
        super().closeEvent(event)
