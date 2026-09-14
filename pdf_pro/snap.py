"""Alignment snap guides in PDF-point space."""

from __future__ import annotations

from typing import Iterable, Optional

from pdf_pro.constants import SNAP_THRESHOLD_PT
from pdf_pro.overlay import OverlayItem


def snap_rect(
    x: float,
    y: float,
    width: float,
    height: float,
    others: Iterable[OverlayItem],
    page_width: float,
    page_height: float,
    threshold: float = SNAP_THRESHOLD_PT,
) -> tuple[float, float, list[tuple[str, float]]]:
    """Return possibly-snapped (x, y) and a list of guide descriptors."""
    guides: list[tuple[str, float]] = []
    cx = x + width / 2
    cy = y + height / 2

    targets_x = [0.0, page_width / 2, page_width]
    targets_y = [0.0, page_height / 2, page_height]
    for item in others:
        targets_x.extend([item.x, item.x + item.width / 2, item.x + item.width])
        targets_y.extend([item.y, item.y + item.height / 2, item.y + item.height])

    best_dx = 0.0
    best_ax = None
    for tx in targets_x:
        for val in (x, cx, x + width):
            d = tx - val
            if abs(d) <= threshold and (best_ax is None or abs(d) < abs(best_dx)):
                best_dx = d
                best_ax = tx
    if best_ax is not None:
        x += best_dx
        guides.append(("v", best_ax))

    best_dy = 0.0
    best_ay = None
    for ty in targets_y:
        for val in (y, cy, y + height):
            d = ty - val
            if abs(d) <= threshold and (best_ay is None or abs(d) < abs(best_dy)):
                best_dy = d
                best_ay = ty
    if best_ay is not None:
        y += best_dy
        guides.append(("h", best_ay))

    return x, y, guides
