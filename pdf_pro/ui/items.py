"""Qt overlay graphics: selection handles, move/resize, editor tint."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

from pdf_pro.overlay import OverlayItem


HANDLE = 8.0
EDITOR_TINT = QColor(40, 120, 220, 40)
SELECT_PEN = QPen(QColor(30, 90, 200), 1.2)
COVER_PEN = QPen(QColor(180, 80, 20), 1.2, Qt.DashLine)


def _qcolor(hex_color: str, alpha: int = 255) -> QColor:
    c = QColor(hex_color or "#000000")
    c.setAlpha(alpha)
    return c


class OverlayGraphics(QGraphicsObject):
    moved = Signal(str, float, float)
    resized = Signal(str, float, float, float, float)
    selected_id = Signal(str)
    about_to_edit = Signal()
    text_edit_requested = Signal(str)

    def __init__(self, item: OverlayItem, zoom: float, parent=None) -> None:
        super().__init__(parent)
        self.item = item
        self.zoom = zoom
        self._dragging = False
        self._resizing = False
        self._last = QPointF()
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._apply_pos()

    def _apply_pos(self) -> None:
        self.setPos(self.item.x * self.zoom, self.item.y * self.zoom)

    def set_zoom(self, zoom: float) -> None:
        self.zoom = zoom
        self._apply_pos()
        self.prepareGeometryChange()
        self.update()

    def sync_from_model(self) -> None:
        self._apply_pos()
        self.prepareGeometryChange()
        self.update()

    def scene_size(self) -> tuple[float, float]:
        return self.item.width * self.zoom, self.item.height * self.zoom

    def boundingRect(self) -> QRectF:
        w, h = self.scene_size()
        pad = HANDLE
        return QRectF(-pad, -pad, w + pad * 2, h + pad * 2)

    def _body(self) -> QRectF:
        w, h = self.scene_size()
        return QRectF(0, 0, max(w, 1), max(h, 1))

    def _handle_rect(self) -> QRectF:
        w, h = self.scene_size()
        return QRectF(w - HANDLE / 2, h - HANDLE / 2, HANDLE, HANDLE)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        body = self._body()
        kind = self.item.type
        data = self.item.data or {}
        if kind == "whiteout":
            painter.fillRect(body, _qcolor(data.get("color") or "#FFFFFF"))
            painter.fillRect(body, EDITOR_TINT)
        elif kind == "cover_replace":
            painter.fillRect(body, _qcolor(data.get("fill") or "#FFFFFF"))
            painter.fillRect(body, QColor(220, 140, 40, 50))
            self._paint_text(painter, body, data)
        elif kind == "text":
            painter.fillRect(body, QColor(255, 255, 200, 60))
            self._paint_text(painter, body, data)
        elif kind in ("image", "signature"):
            pix = self._pixmap()
            if pix:
                painter.drawPixmap(body.toRect(), pix)
            else:
                painter.fillRect(body, QColor(230, 230, 255, 80))
            painter.fillRect(body, EDITOR_TINT)
            if kind == "signature":
                painter.setPen(QPen(QColor(80, 80, 80, 160), 1, Qt.DotLine))
                painter.drawRect(body)
        painter.setPen(COVER_PEN if kind == "cover_replace" else SELECT_PEN)
        if self.isSelected():
            painter.drawRect(body)
            painter.fillRect(self._handle_rect(), QColor(30, 90, 200))
        else:
            painter.setPen(QPen(QColor(30, 90, 200, 90), 1, Qt.DashLine))
            painter.drawRect(body)

    def _paint_text(self, painter: QPainter, body: QRectF, data: dict) -> None:
        font = QFont(data.get("font_family") or "DejaVu Sans")
        # font size is in PDF points; scene is PDF points * zoom
        font.setPointSizeF(max(4.0, float(data.get("font_size") or 12) * self.zoom * 0.75))
        font.setBold(bool(data.get("bold")))
        painter.setFont(font)
        painter.setPen(_qcolor(data.get("color") or "#000000"))
        painter.drawText(body.adjusted(2, 1, -2, -1), Qt.TextWordWrap, str(data.get("text") or ""))

    def _pixmap(self) -> QPixmap | None:
        import base64

        b64 = (self.item.data or {}).get("png_b64") or ""
        if not b64:
            return None
        try:
            pix = QPixmap()
            pix.loadFromData(base64.b64decode(b64))
            return pix
        except Exception:
            return None

    def mousePressEvent(self, event) -> None:
        self.selected_id.emit(self.item.id)
        self.about_to_edit.emit()
        if self._handle_rect().contains(event.pos()):
            self._resizing = True
            self._last = event.scenePos()
            event.accept()
            return
        self._dragging = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._resizing:
            delta = event.scenePos() - self._last
            self._last = event.scenePos()
            nw = max(8.0, self.item.width + delta.x() / self.zoom)
            nh = max(8.0, self.item.height + delta.y() / self.zoom)
            if self.item.type in ("image", "signature") and (self.item.data or {}).get("aspect_lock", True):
                if self.item.width > 0:
                    nh = nw * (self.item.height / self.item.width)
            self.item.width = nw
            self.item.height = nh
            self.prepareGeometryChange()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._resizing:
            self._resizing = False
            self.resized.emit(self.item.id, self.item.x, self.item.y, self.item.width, self.item.height)
            event.accept()
            return
        # commit move
        self.item.x = self.pos().x() / self.zoom
        self.item.y = self.pos().y() / self.zoom
        self.moved.emit(self.item.id, self.item.x, self.item.y)
        self._dragging = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if self.item.type in ("text", "cover_replace"):
            self.text_edit_requested.emit(self.item.id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
