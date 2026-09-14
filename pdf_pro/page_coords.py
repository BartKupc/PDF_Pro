"""Map overlay coordinates from visual (rotation-applied) space to unrotated PDF space.

The editor renders with page.get_pixmap() / page.rect, so overlay x/y/w/h live in
visual space. PyMuPDF draw/insert APIs write in unrotated PDF space.
"""

from __future__ import annotations

from typing import Any


def derotate_xy(
    x: float, y: float, rotation: int, vis_w: float, vis_h: float
) -> tuple[float, float]:
    rot = int(rotation) % 360
    if rot == 90:
        return (y, vis_w - x)
    if rot == 180:
        return (vis_w - x, vis_h - y)
    if rot == 270:
        return (vis_h - y, x)
    return (x, y)


def derotate_rect(
    x: float,
    y: float,
    w: float,
    h: float,
    rotation: int,
    vis_w: float,
    vis_h: float,
) -> tuple[float, float, float, float]:
    corners = ((x, y), (x + w, y), (x, y + h), (x + w, y + h))
    pts = [derotate_xy(px, py, rotation, vis_w, vis_h) for px, py in corners]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0 = min(xs), min(ys)
    return (x0, y0, max(xs) - x0, max(ys) - y0)


def _page_rotation(page: Any) -> int:
    return int(getattr(page, "rotation", 0) or 0) % 360


def overlay_point(page: Any, x: float, y: float) -> tuple[float, float]:
    m = getattr(page, "derotation_matrix", None)
    if m is not None:
        try:
            import fitz

            p = fitz.Point(x, y) * m
            return (float(p.x), float(p.y))
        except Exception:
            pass
    rect = getattr(page, "rect", None)
    vis_w = float(getattr(rect, "width", 0) or 0)
    vis_h = float(getattr(rect, "height", 0) or 0)
    return derotate_xy(x, y, _page_rotation(page), vis_w, vis_h)


def overlay_rect(page: Any, item: Any) -> tuple[float, float, float, float]:
    """Unrotated PDF rect (x0, y0, x1, y1) for a visual-space overlay item."""
    m = getattr(page, "derotation_matrix", None)
    if m is not None:
        try:
            import fitz

            r = fitz.Rect(item.x, item.y, item.x + item.width, item.y + item.height) * m
            r.normalize()
            return (float(r.x0), float(r.y0), float(r.x1), float(r.y1))
        except Exception:
            pass
    rect = getattr(page, "rect", None)
    vis_w = float(getattr(rect, "width", 0) or 0)
    vis_h = float(getattr(rect, "height", 0) or 0)
    x, y, w, h = derotate_rect(
        item.x, item.y, item.width, item.height, _page_rotation(page), vis_w, vis_h
    )
    return (x, y, x + w, y + h)
