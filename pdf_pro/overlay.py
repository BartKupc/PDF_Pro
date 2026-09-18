"""JSON-serialisable overlay document. Coordinates are PDF points, origin top-left."""

from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

ITEM_TYPES = ("text", "whiteout", "cover_replace", "image", "signature", "shape")
SHAPE_KINDS = (
    "rect",
    "line",
    "arrow",
    "ellipse",
    "highlight",
    "underline",
    "strike",
    "freehand",
)


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class OverlayItem:
    id: str
    type: str
    page: int
    x: float
    y: float
    width: float
    height: float
    data: dict[str, Any] = field(default_factory=dict)
    rotation: float = 0.0

    def __post_init__(self) -> None:
        if self.type not in ITEM_TYPES:
            raise ValueError(f"Unknown overlay type: {self.type}")
        if self.width < 0 or self.height < 0:
            raise ValueError("Overlay size must be non-negative")
        if self.page < 0:
            raise ValueError("Page index must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "page": int(self.page),
            "x": float(self.x),
            "y": float(self.y),
            "width": float(self.width),
            "height": float(self.height),
            "rotation": float(self.rotation),
            "data": copy.deepcopy(self.data),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "OverlayItem":
        return cls(
            id=str(raw.get("id") or _new_id()),
            type=str(raw["type"]),
            page=int(raw["page"]),
            x=float(raw["x"]),
            y=float(raw["y"]),
            width=float(raw["width"]),
            height=float(raw["height"]),
            rotation=float(raw.get("rotation") or 0),
            data=copy.deepcopy(raw.get("data") or {}),
        )

    def copy(self) -> "OverlayItem":
        return OverlayItem.from_dict(self.to_dict())

    def rect(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.width, self.height)

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height


def _text_style(
    text: str,
    font_family: str,
    font_size: float,
    color: str,
    bold: bool,
    italic: bool = False,
    underline: bool = False,
    align: str = "left",
    background: str = "",
    opacity: float = 1.0,
) -> dict:
    align_n = (align or "left").lower()
    if align_n not in ("left", "center", "right"):
        align_n = "left"
    return {
        "text": text,
        "font_family": font_family,
        "font_size": font_size,
        "color": color,
        "bold": bool(bold),
        "italic": bool(italic),
        "underline": bool(underline),
        "align": align_n,
        "background": background or "",
        "opacity": float(opacity),
    }


def make_text(
    page: int,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str = "",
    font_family: str = "DejaVu Sans",
    font_size: float = 12,
    color: str = "#000000",
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    align: str = "left",
    background: str = "",
    opacity: float = 1.0,
) -> OverlayItem:
    return OverlayItem(
        id=_new_id(),
        type="text",
        page=page,
        x=x,
        y=y,
        width=width,
        height=height,
        data=_text_style(
            text, font_family, font_size, color, bold, italic, underline, align, background, opacity
        ),
    )


def make_whiteout(
    page: int, x: float, y: float, width: float, height: float, color: str = "#FFFFFF"
) -> OverlayItem:
    return OverlayItem(
        id=_new_id(),
        type="whiteout",
        page=page,
        x=x,
        y=y,
        width=width,
        height=height,
        data={"color": color},
    )


def make_cover_replace(
    page: int,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str = "",
    font_family: str = "DejaVu Sans",
    font_size: float = 12,
    color: str = "#000000",
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    align: str = "left",
    background: str = "",
    opacity: float = 1.0,
    fill: str = "#FFFFFF",
) -> OverlayItem:
    data = _text_style(
        text, font_family, font_size, color, bold, italic, underline, align, background, opacity
    )
    data["fill"] = fill
    return OverlayItem(
        id=_new_id(),
        type="cover_replace",
        page=page,
        x=x,
        y=y,
        width=width,
        height=height,
        data=data,
    )


def make_image(
    page: int,
    x: float,
    y: float,
    width: float,
    height: float,
    png_b64: str,
    aspect_lock: bool = True,
) -> OverlayItem:
    return OverlayItem(
        id=_new_id(),
        type="image",
        page=page,
        x=x,
        y=y,
        width=width,
        height=height,
        data={"png_b64": png_b64, "aspect_lock": bool(aspect_lock)},
    )


def make_signature(
    page: int,
    x: float,
    y: float,
    width: float,
    height: float,
    kind: str,
    png_b64: str = "",
    strokes: Optional[list] = None,
    text: str = "",
    font_family: str = "Dancing Script",
    vault_id: str = "",
    date: str = "",
    label: str = "",
) -> OverlayItem:
    return OverlayItem(
        id=_new_id(),
        type="signature",
        page=page,
        x=x,
        y=y,
        width=width,
        height=height,
        data={
            "kind": kind,
            "png_b64": png_b64,
            "strokes": strokes or [],
            "text": text,
            "font_family": font_family,
            "vault_id": vault_id,
            "date": date,
            "label": label,
        },
    )


def make_shape(
    page: int,
    x: float,
    y: float,
    width: float,
    height: float,
    kind: str,
    *,
    stroke: str = "#000000",
    fill: str = "",
    width_pt: float = 1.5,
    opacity: float = 1.0,
    points: Optional[list] = None,
) -> OverlayItem:
    if kind not in SHAPE_KINDS:
        raise ValueError(f"Unknown shape kind: {kind}")
    return OverlayItem(
        id=_new_id(),
        type="shape",
        page=page,
        x=x,
        y=y,
        width=width,
        height=height,
        data={
            "kind": kind,
            "stroke": stroke,
            "fill": fill,
            "width_pt": float(width_pt),
            "opacity": float(opacity),
            "points": points or [],
        },
    )


class OverlayDocument:
    def __init__(
        self,
        source_path: str = "",
        source_sha256: str = "",
        page_count: int = 0,
        items: Optional[list[OverlayItem]] = None,
    ) -> None:
        self.source_path = source_path
        self.source_sha256 = source_sha256
        self.page_count = page_count
        self.items: list[OverlayItem] = items or []

    def add(self, item: OverlayItem) -> OverlayItem:
        self.items.append(item)
        return item

    def remove(self, item_id: str) -> Optional[OverlayItem]:
        for i, item in enumerate(self.items):
            if item.id == item_id:
                return self.items.pop(i)
        return None

    def get(self, item_id: str) -> Optional[OverlayItem]:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def items_on_page(self, page: int) -> list[OverlayItem]:
        return [i for i in self.items if i.page == page]

    def hit_test(self, page: int, px: float, py: float) -> Optional[OverlayItem]:
        for item in reversed(self.items_on_page(page)):
            if item.contains(px, py):
                return item
        return None

    def replace_all(self, items: Iterable[OverlayItem]) -> None:
        self.items = [i.copy() for i in items]

    def snapshot(self) -> list[dict[str, Any]]:
        return [i.to_dict() for i in self.items]

    def restore(self, snap: list[dict[str, Any]]) -> None:
        self.items = [OverlayItem.from_dict(d) for d in snap]

    def has_signature(self) -> bool:
        return any(i.type == "signature" for i in self.items)

    def has_cover_replace(self) -> bool:
        return any(i.type == "cover_replace" for i in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "page_count": self.page_count,
            "items": [i.to_dict() for i in self.items],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "OverlayDocument":
        doc = cls(
            source_path=str(raw.get("source_path") or ""),
            source_sha256=str(raw.get("source_sha256") or ""),
            page_count=int(raw.get("page_count") or 0),
        )
        doc.items = [OverlayItem.from_dict(x) for x in raw.get("items") or []]
        return doc

    @classmethod
    def from_json(cls, text: str) -> "OverlayDocument":
        return cls.from_dict(json.loads(text))
