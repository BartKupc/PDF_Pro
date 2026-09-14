"""Progressive page renderer on a worker thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QImage

from pdf_pro.render_kind import KIND_PAGE


class RenderEngine(QObject):
    page_ready = Signal(int, float, QImage, float, float, str)  # index, scale, image, pdf_w, pdf_h, kind
    failed = Signal(str)
    request = Signal(int, float, str)

    def __init__(self) -> None:
        super().__init__()
        self._doc = None
        self.request.connect(self.render)

    def set_doc(self, opened) -> None:
        self._doc = opened

    @Slot(int, float, str)
    def render(self, index: int, scale: float, kind: str = KIND_PAGE) -> None:
        doc = self._doc
        if doc is None:
            return
        try:
            if index < 0 or index >= doc.page_count:
                return
            pix = doc.render_pixmap(index, scale=scale)
            fmt = QImage.Format_RGB888
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
            w, h = doc.page_size(index)
            self.page_ready.emit(index, scale, img, w, h, kind)
        except Exception as exc:
            self.failed.emit(str(exc))


class RenderThread(QThread):
    def __init__(self, engine: RenderEngine) -> None:
        super().__init__()
        self.engine = engine
        engine.moveToThread(self)
