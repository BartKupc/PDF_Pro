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
from pdf_pro.page_plan import PagePlan


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


def _align_const(align: str):
    import fitz

    a = (align or "left").lower()
    if a == "center":
        return fitz.TEXT_ALIGN_CENTER
    if a == "right":
        return fitz.TEXT_ALIGN_RIGHT
    return fitz.TEXT_ALIGN_LEFT


def _insert_text(page, item: OverlayItem, data: dict) -> None:
    import fitz

    family = resolve_family(data.get("font_family") or "DejaVu Sans")
    bold = bool(data.get("bold"))
    path = font_path(family, bold=bold)
    fontsize = float(data.get("font_size") or 12)
    color = _hex_to_rgb(data.get("color") or "#000000")
    text = str(data.get("text") or "")
    rect = _item_rect(page, item)
    opacity = float(data.get("opacity") if data.get("opacity") is not None else 1.0)
    bg = data.get("background") or ""
    if bg:
        page.draw_rect(rect, color=None, fill=_hex_to_rgb(bg), width=0, fill_opacity=max(0.0, min(1.0, opacity)))
    fontname = f"f_{family.replace(' ', '_')}_{'b' if bold else 'r'}"
    try:
        page.insert_font(fontname=fontname, fontfile=path.as_posix())
    except Exception:
        fontname = "heit" if data.get("italic") else "helv"
    morph = None
    if data.get("italic"):
        morph = (fitz.Point(rect.x0, rect.y1), fitz.Matrix(1, 0, 0.25, 1, 0, 0))
    kwargs = dict(
        fontname=fontname,
        fontsize=fontsize,
        color=color,
        align=_align_const(str(data.get("align") or "left")),
        rotate=_page_rotate(page),
    )
    if morph is not None:
        kwargs["morph"] = morph
    page.insert_textbox(rect, text, **kwargs)
    if data.get("underline") and text:
        y = min(rect.y1 - 1, rect.y0 + fontsize * 1.15)
        page.draw_line(fitz.Point(rect.x0, y), fitz.Point(rect.x1, y), color=color, width=0.6)


def _insert_image(page, item: OverlayItem, png_b64: str) -> None:
    if not png_b64:
        return
    raw = base64.b64decode(png_b64)
    rotate = (_page_rotate(page) + int(item.rotation or 0)) % 360
    page.insert_image(
        _item_rect(page, item),
        stream=raw,
        keep_proportion=False,
        rotate=rotate,
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


def _draw_arrowhead(page, x0, y0, x1, y1, color, width_pt) -> None:
    import math

    import fitz

    ang = math.atan2(y1 - y0, x1 - x0)
    size = max(6.0, width_pt * 4)
    left = fitz.Point(x1 - size * math.cos(ang - 0.4), y1 - size * math.sin(ang - 0.4))
    right = fitz.Point(x1 - size * math.cos(ang + 0.4), y1 - size * math.sin(ang + 0.4))
    page.draw_polyline([left, fitz.Point(x1, y1), right], color=color, width=width_pt, closePath=False)


def _draw_shape(page, item: OverlayItem) -> None:
    import fitz

    data = item.data or {}
    kind = str(data.get("kind") or "rect")
    stroke = _hex_to_rgb(data.get("stroke") or "#000000")
    fill_raw = data.get("fill") or ""
    fill = _hex_to_rgb(fill_raw) if fill_raw else None
    width_pt = float(data.get("width_pt") or 1.5)
    opacity = float(data.get("opacity") if data.get("opacity") is not None else 1.0)
    rect = _item_rect(page, item)
    x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
    if kind == "highlight":
        fill = fill or (1, 1, 0)
        page.draw_rect(rect, color=None, fill=fill, width=0, fill_opacity=min(0.45, opacity))
        return
    if kind == "underline":
        y = y1 - 1
        page.draw_line(fitz.Point(x0, y), fitz.Point(x1, y), color=stroke, width=max(1.0, width_pt))
        return
    if kind == "strike":
        y = (y0 + y1) / 2
        page.draw_line(fitz.Point(x0, y), fitz.Point(x1, y), color=stroke, width=max(1.0, width_pt))
        return
    if kind == "line":
        page.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1), color=stroke, width=width_pt)
        return
    if kind == "arrow":
        page.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1), color=stroke, width=width_pt)
        _draw_arrowhead(page, x0, y0, x1, y1, stroke, width_pt)
        return
    if kind == "ellipse":
        page.draw_oval(rect, color=stroke, fill=fill, width=width_pt if fill is None else 0, fill_opacity=opacity)
        return
    if kind == "freehand":
        pts = data.get("points") or []
        if len(pts) < 2:
            return
        shape = page.new_shape()
        prev = None
        for p in pts:
            if isinstance(p, dict):
                lx, ly = float(p.get("x", 0)), float(p.get("y", 0))
            else:
                lx, ly = float(p[0]), float(p[1])
            vx = item.x + lx * item.width
            vy = item.y + ly * item.height
            x, y = overlay_point(page, vx, vy)
            if prev is not None:
                shape.draw_line(fitz.Point(*prev), fitz.Point(x, y))
            prev = (x, y)
        shape.finish(color=stroke, width=width_pt, stroke_opacity=opacity)
        shape.commit()
        return
    # rect / black box
    page.draw_rect(
        rect,
        color=stroke if fill is None else fill,
        fill=fill,
        width=0 if fill is not None else width_pt,
        fill_opacity=opacity if fill is not None else 1,
    )


def _draw_signature_caption(page, item: OverlayItem, data: dict) -> None:
    import fitz

    bits = [str(data.get("label") or "").strip(), str(data.get("date") or "").strip()]
    bits = [b for b in bits if b]
    if not bits:
        return
    caption = "  ·  ".join(bits)
    rect = _item_rect(page, item)
    cap = fitz.Rect(rect.x0, rect.y1 + 1, rect.x1 + 80, rect.y1 + 16)
    page.insert_textbox(cap, caption, fontname="helv", fontsize=8, color=(0.15, 0.15, 0.15))


def apply_item(page, item: OverlayItem) -> None:
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
        from pdf_pro.signature_feedback import signature_paint_source

        source = signature_paint_source(data)
        if source == "png":
            _insert_image(page, item, data.get("png_b64") or "")
        elif source == "strokes":
            _draw_strokes(page, item, data.get("strokes") or [])
        elif source == "text":
            _insert_text(page, item, {**data, "font_family": data.get("font_family") or "Dancing Script"})
        _draw_signature_caption(page, item, data)
    elif item.type == "shape":
        _draw_shape(page, item)
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


def _atomic_save(work, dest: Path) -> None:
    dest = Path(dest)
    tmp = dest.with_name(dest.name + ".partial")
    try:
        if tmp.exists():
            tmp.unlink()
        work.save(tmp.as_posix(), garbage=4, deflate=True)
        os.replace(tmp.as_posix(), dest.as_posix())
    except Exception as exc:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise ExportError(f"Could not write export: {exc}") from exc


def export_pdf(
    source: Path,
    overlay: OverlayDocument,
    dest: Path,
    password: Optional[str] = None,
    plan: Optional[PagePlan] = None,
    passwords: Optional[dict] = None,
    progress=None,
) -> Path:
    source = Path(source).resolve()
    dest = Path(dest).resolve()
    if dest == source:
        raise ExportError("Refusing to overwrite the source PDF")
    if dest.exists() and dest.samefile(source):
        raise ExportError("Refusing to overwrite the source PDF")

    before = file_sha256(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if progress:
        progress(5, "Opening source")

    work = None
    try:
        if plan is not None and plan.pages:
            from pdf_pro.compose import ComposeError, compose_work_doc

            pwmap = dict(passwords or {})
            if password:
                pwmap.setdefault(str(source), password)
                pwmap.setdefault(source.as_posix(), password)
            try:
                work = compose_work_doc(plan, passwords=pwmap)
            except ComposeError as exc:
                raise ExportError(str(exc)) from exc
        else:
            import fitz

            data = source.read_bytes()
            work = fitz.open(stream=data, filetype="pdf")
            if work.is_encrypted:
                if not password or not work.authenticate(password):
                    work.close()
                    raise ExportError("Could not decrypt PDF for export")
        if progress:
            progress(40, "Flattening overlays")
        flatten_overlays(work, overlay)
        if progress:
            progress(70, "Writing file")
        _atomic_save(work, dest)
    finally:
        if work is not None:
            try:
                work.close()
            except Exception:
                pass

    after = file_sha256(source)
    if after != before:
        raise ExportError("Source file changed during export — aborting")

    if progress:
        progress(85, "Validating export")
    try:
        validate_export(dest)
    except Exception as exc:
        raise ExportError(f"Export was written but failed validation: {exc}") from exc
    if progress:
        progress(100, "Done")
    return dest
