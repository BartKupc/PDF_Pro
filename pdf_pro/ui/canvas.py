from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPixmap, QTransform, QColor, QPen
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QRubberBand

from pdf_pro.overlay import OverlayDocument, OverlayItem
from pdf_pro.snap import snap_rect
from pdf_pro.ui.items import OverlayGraphics


class PageCanvas(QGraphicsView):
    overlay_changed = Signal()
    edit_starting = Signal()
    text_edit_requested = Signal(str)
    page_clicked = Signal(float, float)  # PDF points
    rubber_finished = Signal(float, float, float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self._pix_item = QGraphicsPixmapItem()
        self.scene.addItem(self._pix_item)
        self.zoom = 1.25
        self.view_rotation = 0
        self.page_index = 0
        self.page_w = 612.0
        self.page_h = 792.0
        self.overlay = OverlayDocument()
        self._graphics: dict[str, OverlayGraphics] = {}
        self._tool = "select"
        self._rubber = None
        self._rubber_origin = None
        self._guides: list[tuple[str, float]] = []
        self.setAcceptDrops(False)

    def set_tool(self, tool: str) -> None:
        self._tool = tool
        self.setCursor(Qt.CrossCursor if tool != "select" else Qt.ArrowCursor)

    def set_page_image(self, image, pdf_w: float, pdf_h: float, scale: float) -> None:
        pix = QPixmap.fromImage(image)
        self._pix_item.setPixmap(pix)
        self.page_w = pdf_w
        self.page_h = pdf_h
        # pixmap pixels cover pdf * scale; map into scene = pdf * zoom
        if scale > 0:
            factor = self.zoom / scale
            self._pix_item.setScale(factor)
        self._pix_item.setZValue(-1)
        self.scene.setSceneRect(0, 0, pdf_w * self.zoom, pdf_h * self.zoom)
        self._rebuild_overlays()

    def bind_overlay(self, overlay: OverlayDocument) -> None:
        self.overlay = overlay
        self._rebuild_overlays()

    def _rebuild_overlays(self) -> None:
        for g in self._graphics.values():
            self.scene.removeItem(g)
        self._graphics.clear()
        for item in self.overlay.items_on_page(self.page_index):
            g = OverlayGraphics(item, self.zoom)
            g.moved.connect(self._on_moved)
            g.resized.connect(self._on_resized)
            g.about_to_edit.connect(self._on_about_to_edit)
            g.text_edit_requested.connect(self.text_edit_requested.emit)
            self.scene.addItem(g)
            self._graphics[item.id] = g

    def _on_about_to_edit(self) -> None:
        self.edit_starting.emit()

    def _on_moved(self, item_id: str, x: float, y: float) -> None:
        item = self.overlay.get(item_id)
        if not item:
            return
        others = [i for i in self.overlay.items_on_page(self.page_index) if i.id != item_id]
        nx, ny, guides = snap_rect(x, y, item.width, item.height, others, self.page_w, self.page_h)
        item.x, item.y = nx, ny
        self._guides = guides
        g = self._graphics.get(item_id)
        if g:
            g.sync_from_model()
        self.viewport().update()
        self.overlay_changed.emit()

    def _on_resized(self, item_id, x, y, w, h) -> None:
        item = self.overlay.get(item_id)
        if not item:
            return
        item.x, item.y, item.width, item.height = x, y, w, h
        self.overlay_changed.emit()

    def pdf_pos(self, view_pos) -> tuple[float, float]:
        sp = self.mapToScene(view_pos)
        if self.zoom == 0:
            return 0.0, 0.0
        return sp.x() / self.zoom, sp.y() / self.zoom

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        if self._tool in ("whiteout", "cover", "text"):
            self._rubber_origin = event.pos()
            self._rubber = QRubberBand(QRubberBand.Rectangle, self)
            self._rubber.setGeometry(event.pos().x(), event.pos().y(), 1, 1)
            self._rubber.show()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._rubber and self._rubber_origin:
            x0, y0 = self._rubber_origin.x(), self._rubber_origin.y()
            x1, y1 = event.pos().x(), event.pos().y()
            self._rubber.setGeometry(
                min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._rubber and self._rubber_origin:
            x0, y0 = self.pdf_pos(self._rubber_origin)
            x1, y1 = self.pdf_pos(event.pos())
            self._rubber.hide()
            self._rubber = None
            self._rubber_origin = None
            x, y = min(x0, x1), min(y0, y1)
            w, h = abs(x1 - x0), abs(y1 - y0)
            if w > 2 and h > 2:
                self.rubber_finished.emit(x, y, w, h)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def drawForeground(self, painter: QPainter, rect) -> None:
        super().drawForeground(painter, rect)
        if not self._guides:
            return
        painter.setPen(QPen(QColor(255, 80, 80, 180), 0, Qt.DashLine))
        for kind, val in self._guides:
            if kind == "v":
                x = val * self.zoom
                painter.drawLine(x, 0, x, self.page_h * self.zoom)
            else:
                y = val * self.zoom
                painter.drawLine(0, y, self.page_w * self.zoom, y)

    def selected_item(self) -> OverlayItem | None:
        for g in self._graphics.values():
            if g.isSelected():
                return g.item
        return None

    def apply_view_rotation(self) -> None:
        t = QTransform()
        t.rotate(self.view_rotation)
        self.setTransform(t)
