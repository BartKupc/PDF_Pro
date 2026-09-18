"""Scan-only pages and missing-font notices (FR-V7 polish, FR-E5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


SCAN_ONLY_NOTICE = (
    "This page looks like a scan (little or no selectable text). "
    "Search and copy are limited. Use Cover-and-replace to amend it."
)
MISSING_FONT_NOTICE = (
    "This PDF references fonts that are not embedded. Text operations on "
    "affected pages may not match the original appearance."
)


@dataclass(frozen=True)
class PageWarning:
    page: int
    kind: str
    message: str


def page_is_scan_only(text: str, image_count: int = 0) -> bool:
    stripped = (text or "").strip()
    if len(stripped) >= 8:
        return False
    if image_count > 0:
        return True
    return len(stripped) == 0


def missing_fonts_from_list(fonts: Iterable[tuple]) -> list[str]:
    """fonts: page.get_fonts() tuples (xref, ext, type, name, ...)."""
    missing = []
    for row in fonts:
        name = ""
        ext = ""
        if len(row) >= 4:
            ext = str(row[1] or "")
            name = str(row[3] or "")
        if name and (not ext or ext.upper() in {"", "N/A", "NONE"}):
            missing.append(name)
    return missing


def warnings_for_pages(
    pages: Iterable[tuple[int, str, int, list]],
) -> list[PageWarning]:
    """pages: (index, text, image_count, font_tuples)."""
    out: list[PageWarning] = []
    seen_fonts: set[str] = set()
    for index, text, images, fonts in pages:
        if page_is_scan_only(text, images):
            out.append(PageWarning(index, "scan", SCAN_ONLY_NOTICE))
        for name in missing_fonts_from_list(fonts):
            if name not in seen_fonts:
                seen_fonts.add(name)
                out.append(PageWarning(index, "font", f"{MISSING_FONT_NOTICE} ({name})"))
    return out


def scan_fitz_doc(doc: Any) -> list[PageWarning]:
    rows = []
    for i, page in enumerate(doc):
        try:
            text = page.get_text("text") or ""
        except Exception:
            text = ""
        try:
            images = len(page.get_images() or [])
        except Exception:
            images = 0
        try:
            fonts = list(page.get_fonts() or [])
        except Exception:
            fonts = []
        rows.append((i, text, images, fonts))
    return warnings_for_pages(rows)
