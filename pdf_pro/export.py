"""Flatten overlays into a NEW PDF. Never overwrite the source. Validate by reopening."""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Optional

from pdf_pro.document import file_sha256, open_pdf
from pdf_pro.fonts import font_path, resolve_family
from pdf_pro.overlay import OverlayDocument, OverlayItem
from pdf_pro.page_coords import overlay_point, overlay_rect


class ExportError(Exception):
    pass


def assert_export_destination(source: Path, dest: Path) -> Path:
    """Preflight an export path. Always raises ExportError with reason + path."""
    source = Path(source)
    dest = Path(dest)
    try:
        same = dest.resolve() == source.resolve()
    except OSError:
        same = dest.expanduser().absolute() == source.expanduser().absolute()
    if same:
        raise ExportError(f"Refusing to overwrite the source PDF.\nPath: {dest}")
    parent = dest.parent
    if not parent.exists():
        raise ExportError(f"Export folder does not exist.\nPath: {parent}")
    if not os.access(parent, os.W_OK):
        raise ExportError(f"Cannot write export — folder is not writable.\nPath: {parent}")
    return dest


def default_export_path(source: Path, overlay: OverlayDocument) -> Path:
    suffix = "_signed.pdf" if overlay.has_signature() else "_amended.pdf"
    return source.with_name(source.stem + suffix)


def _hex_to_rgb(color: str) -> tuple[float, float, float]:
    c = (color or "#000000").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return (0, 0, 0)
    r = int(c[0:2], 16) / 255.0
    g = int(c[2:4], 16) / 255.0
    b = int(c[4:6], 16) / 255.0
    return (r, g, b)


def _item_rect(page, item: OverlayItem):
    import fitz

    x0, y0, x1, y1 = overlay_rect(page, item)
    return fitz.Rect(x0, y0, x1, y1)


def _page_rotate(page) -> int:
    return int(getattr(page, "rotation", 0) or 0) % 360


def _insert_text(page, item: OverlayItem, data: dict) -> None:
    import fitz

    family = resolve_family(data.get("font_family") or "DejaVu Sans")
    bold = bool(data.get("bold"))
    path = font_path(family, bold=bold)
    fontsize = float(data.get("font_size") or 12)
    color = _hex_to_rgb(data.get("color") or "#000000")
    text = str(data.get("text") or "")
    rect = _item_rect(page, item)
    fontname = f"f_{family.replace(' ', '_')}_{'b' if bold else 'r'}"
    try:
        page.insert_font(fontname=fontname, fontfile=path.as_posix())
    except Exception:
        fontname = "helv"
    page.insert_textbox(
        rect,
        text,
        fontname=fontname,
        fontsize=fontsize,
        color=color,
        align=fitz.TEXT_ALIGN_LEFT,
        rotate=_page_rotate(page),
    )


def _insert_image(page, item: OverlayItem, png_b64: str) -> None:
    if not png_b64:
        return
    raw = base64.b64decode(png_b64)
    page.insert_image(
        _item_rect(page, item),
        stream=raw,
        keep_proportion=False,
        rotate=_page_rotate(page),
    )


def _draw_strokes(page, item: OverlayItem, strokes: list) -> None:
    import fitz

    if not strokes:
        return
    # strokes are in item-local 0..1 coordinates
    shape = page.new_shape()
    for stroke in strokes:
        if not stroke:
            continue
        pts = []
        for p in stroke:
            if isinstance(p, dict):
                lx, ly = float(p.get("x", 0)), float(p.get("y", 0))
                pressure = float(p.get("p", 1) or 1)
            else:
                lx, ly = float(p[0]), float(p[1])
                pressure = float(p[2]) if len(p) > 2 else 1.0
            vx = item.x + lx * item.width
            vy = item.y + ly * item.height
            x, y = overlay_point(page, vx, vy)
            pts.append((x, y, max(0.2, pressure)))
        if len(pts) == 1:
            x, y, pr = pts[0]
            shape.draw_circle(fitz.Point(x, y), 0.6 * pr)
        else:
            for (x0, y0, p0), (x1, y1, p1) in zip(pts, pts[1:]):
                shape.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1))
                shape.finish(color=(0, 0, 0), width=max(0.5, 1.6 * ((p0 + p1) / 2)))
    shape.commit()


def apply_item(page, item: OverlayItem) -> None:
    import fitz

    data = item.data or {}
    if item.type == "whiteout":
        fill = _hex_to_rgb(data.get("color") or "#FFFFFF")
        page.draw_rect(_item_rect(page, item), color=fill, fill=fill, width=0)
    elif item.type == "text":
        _insert_text(page, item, data)
    elif item.type == "cover_replace":
        fill = _hex_to_rgb(data.get("fill") or "#FFFFFF")
        page.draw_rect(_item_rect(page, item), color=fill, fill=fill, width=0)
        _insert_text(page, item, data)
    elif item.type == "image":
        _insert_image(page, item, data.get("png_b64") or "")
    elif item.type == "signature":
        strokes = data.get("strokes") or []
        png = data.get("png_b64") or ""
        if strokes:
            _draw_strokes(page, item, strokes)
        elif png:
            _insert_image(page, item, png)
        elif data.get("text"):
            _insert_text(page, item, {**data, "font_family": data.get("font_family") or "Dancing Script"})
        else:
            pass
    else:
        raise ExportError(f"Unknown overlay type: {item.type}")


def flatten_overlays(doc, overlay: OverlayDocument) -> None:
    by_page: dict[int, list[OverlayItem]] = {}
    for item in overlay.items:
        by_page.setdefault(item.page, []).append(item)
    for index, items in by_page.items():
        if index < 0 or index >= doc.page_count:
            continue
        page = doc[index]
        for item in items:
            apply_item(page, item)


def validate_export(dest: Path, password: Optional[str] = None) -> None:
    opened = open_pdf(dest, password=None)
    try:
        for i in range(opened.page_count):
            pix = opened.render_pixmap(i, scale=0.3)
            if pix.width < 1 or pix.height < 1:
                raise ExportError(f"Export validation failed: page {i + 1} rendered empty")
    finally:
        opened.close()


def export_pdf(
    source: Path,
    overlay: OverlayDocument,
    dest: Path,
    password: Optional[str] = None,
) -> Path:
    source = Path(source).resolve()
    dest = Path(dest).resolve()
    if dest == source:
        raise ExportError("Refusing to overwrite the source PDF")
    if dest.exists() and dest.samefile(source):
        raise ExportError("Refusing to overwrite the source PDF")

    before = file_sha256(source)
    dest.parent.mkdir(parents=True, exist_ok=True)

    opened = open_pdf(source, password=password)
    try:
        import fitz

        # Work on a copy opened from bytes so the source file handle stays read-only.
        data = source.read_bytes()
        work = fitz.open(stream=data, filetype="pdf")
        if work.is_encrypted:
            if not password or not work.authenticate(password):
                work.close()
                raise ExportError("Could not decrypt PDF for export")
        try:
            flatten_overlays(work, overlay)
            try:
                work.save(dest.as_posix(), garbage=4, deflate=True)
            except Exception as exc:
                raise ExportError(f"Could not write export: {exc}") from exc
        finally:
            work.close()
    finally:
        opened.close()

    after = file_sha256(source)
    if after != before:
        raise ExportError("Source file changed during export — aborting")

    try:
        validate_export(dest)
    except Exception as exc:
        raise ExportError(f"Export was written but failed validation: {exc}") from exc
    return dest
