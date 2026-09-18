"""Background preview/export workers. fitz work stays off the UI thread."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from pdf_pro.jobs import render_preview_pages


class PreviewWorker(QThread):
    page_ready = Signal(int, QImage)
    progress = Signal(int, str)
    failed = Signal(str)
    finished_ok = Signal()

    def __init__(self, source: Path, overlay, password, plan=None, parent=None) -> None:
        super().__init__(parent)
        self.source = Path(source)
        self.overlay = overlay
        self.password = password
        self.plan = plan

    def run(self) -> None:
        try:
            def prog(pct, msg):
                self.progress.emit(int(pct), str(msg))

            pages = render_preview_pages(
                self.source, self.overlay, self.password, plan=self.plan, progress=prog
            )
            for i, (_w, _h, png) in enumerate(pages):
                img = QImage.fromData(png, "PNG").copy()
                self.page_ready.emit(i, img)
            self.finished_ok.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class ExportWorker(QThread):
    progress = Signal(int, str)
    failed = Signal(str)
    finished_ok = Signal(object)

    def __init__(self, fn, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn(lambda pct, msg: self.progress.emit(int(pct), str(msg)))
            self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
