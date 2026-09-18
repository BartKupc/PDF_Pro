"""Logical page list for rotate/delete/reorder/duplicate/merge/extract.

Overlays bind to *logical* page index in this plan. Mutators remap overlay
page numbers so items stay on the visual page they were authored against.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from pdf_pro.overlay import OverlayDocument


@dataclass
class PageRef:
    source_path: str
    source_index: int
    rotation: int = 0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_path": self.source_path,
            "source_index": int(self.source_index),
            "rotation": int(self.rotation) % 360,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PageRef":
        return cls(
            id=str(raw.get("id") or uuid.uuid4()),
            source_path=str(raw["source_path"]),
            source_index=int(raw["source_index"]),
            rotation=int(raw.get("rotation") or 0) % 360,
        )


class PagePlan:
    def __init__(self, pages: Optional[list[PageRef]] = None) -> None:
        self.pages: list[PageRef] = list(pages or [])

    def __len__(self) -> int:
        return len(self.pages)

    @classmethod
    def identity(cls, source_path: str, page_count: int) -> "PagePlan":
        return cls([PageRef(source_path=source_path, source_index=i) for i in range(page_count)])

    def to_dict(self) -> dict[str, Any]:
        return {"version": 1, "pages": [p.to_dict() for p in self.pages]}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PagePlan":
        return cls([PageRef.from_dict(p) for p in (raw.get("pages") or [])])

    def _sync_count(self, overlay: Optional[OverlayDocument]) -> None:
        if overlay is not None:
            overlay.page_count = len(self.pages)

    def rotate(self, index: int, degrees: int = 90) -> None:
        page = self.pages[index]
        page.rotation = (page.rotation + int(degrees)) % 360

    def delete_page(self, index: int, overlay: Optional[OverlayDocument] = None) -> None:
        if index < 0 or index >= len(self.pages):
            raise IndexError("page index out of range")
        if len(self.pages) == 1:
            raise ValueError("Cannot delete the last page")
        self.pages.pop(index)
        if overlay is not None:
            overlay.items = [i for i in overlay.items if i.page != index]
            for item in overlay.items:
                if item.page > index:
                    item.page -= 1
            self._sync_count(overlay)

    def duplicate_page(self, index: int, overlay: Optional[OverlayDocument] = None) -> None:
        src = self.pages[index]
        clone = PageRef(source_path=src.source_path, source_index=src.source_index, rotation=src.rotation)
        self.pages.insert(index + 1, clone)
        if overlay is not None:
            copies = []
            for item in overlay.items:
                if item.page == index:
                    copied = item.copy()
                    copied.id = str(uuid.uuid4())
                    copied.page = index + 1
                    copies.append(copied)
                elif item.page > index:
                    item.page += 1
            overlay.items.extend(copies)
            self._sync_count(overlay)

    def reorder(self, order: list[int], overlay: Optional[OverlayDocument] = None) -> None:
        if sorted(order) != list(range(len(self.pages))):
            raise ValueError("reorder must be a permutation of current pages")
        mapping = {old: new for new, old in enumerate(order)}
        self.pages = [self.pages[i] for i in order]
        if overlay is not None:
            for item in overlay.items:
                item.page = mapping[item.page]
            self._sync_count(overlay)

    def move_page(self, src: int, dst: int, overlay: Optional[OverlayDocument] = None) -> None:
        if src == dst:
            return
        order = list(range(len(self.pages)))
        item = order.pop(src)
        if dst > src:
            dst -= 1
        order.insert(dst, item)
        self.reorder(order, overlay=overlay)

    def merge_from(self, source_path: str, page_count: int) -> None:
        for i in range(page_count):
            self.pages.append(PageRef(source_path=source_path, source_index=i))

    def extract(self, indices: list[int]) -> "PagePlan":
        return PagePlan([self.pages[i] for i in indices])
