"""Rotate / layer / duplicate overlay items (FR-A4 rest, FR-S5 rest)."""

from __future__ import annotations

import uuid

from pdf_pro.overlay import OverlayDocument, OverlayItem


def duplicate_item(doc: OverlayDocument, item_id: str, dx: float = 12.0, dy: float = 12.0) -> OverlayItem:
    item = doc.get(item_id)
    if item is None:
        raise KeyError(item_id)
    copied = item.copy()
    copied.id = str(uuid.uuid4())
    copied.x += dx
    copied.y += dy
    doc.add(copied)
    return copied


def rotate_item(item: OverlayItem, degrees: float = 90.0) -> OverlayItem:
    item.rotation = (float(item.rotation) + float(degrees)) % 360.0
    if int(degrees) % 180 != 0:
        item.width, item.height = item.height, item.width
    return item


def bring_to_front(doc: OverlayDocument, item_id: str) -> None:
    item = doc.remove(item_id)
    if item is None:
        raise KeyError(item_id)
    doc.items.append(item)


def send_to_back(doc: OverlayDocument, item_id: str) -> None:
    item = doc.remove(item_id)
    if item is None:
        raise KeyError(item_id)
    doc.items.insert(0, item)


def z_index(doc: OverlayDocument, item_id: str) -> int:
    for i, item in enumerate(doc.items):
        if item.id == item_id:
            return i
    raise KeyError(item_id)
