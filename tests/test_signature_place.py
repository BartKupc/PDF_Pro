"""Signature placement: paint source + export pixels + page routing.

Offscreen Qt integration (SignatureStudio → canvas → flatten) lives in
test_signature_studio_place.py and is skipped without PySide6.
"""

from __future__ import annotations

import base64
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from pdf_pro.overlay import OverlayDocument
from pdf_pro.page_plan import PagePlan
from pdf_pro.signature_feedback import (
    place_signature_on_page,
    signature_paint_source,
)
from pdf_pro.vault import SignatureAsset

try:
    import fitz
except ImportError:
    fitz = None


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def solid_png_b64(width: int = 40, height: int = 16, rgb: tuple[int, int, int] = (0, 0, 0)) -> str:
    """Minimal RGB PNG, no extra deps."""
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(raw)) + _png_chunk(b"IEND", b"")
    return base64.b64encode(png).decode("ascii")


class SignaturePaintSourceTests(unittest.TestCase):
    def test_draw_with_png_and_strokes_uses_png(self):
        data = {
            "kind": "draw",
            "png_b64": "QUFB",
            "strokes": [[{"x": 0, "y": 0, "p": 1}]],
            "text": "",
        }
        self.assertEqual(signature_paint_source(data), "png")

    def test_type_with_png_uses_png(self):
        data = {"kind": "type", "png_b64": "QUFB", "strokes": [], "text": "Bart"}
        self.assertEqual(signature_paint_source(data), "png")

    def test_strokes_only_uses_strokes(self):
        data = {"kind": "draw", "png_b64": "", "strokes": [[{"x": 0.1, "y": 0.2, "p": 1}]]}
        self.assertEqual(signature_paint_source(data), "strokes")

    def test_text_only_uses_text(self):
        data = {"kind": "type", "png_b64": "", "strokes": [], "text": "BK"}
        self.assertEqual(signature_paint_source(data), "text")


class SignaturePlaceRoutingTests(unittest.TestCase):
    def test_place_uses_logical_page_not_source_index(self):
        ov = OverlayDocument(page_count=3)
        asset = SignatureAsset(id="a", name="Bart", kind="type", text="Bart", png_b64=solid_png_b64())
        item = place_signature_on_page(ov, asset, page_index=2, page_w=612, page_h=792)
        self.assertEqual(item.page, 2)
        self.assertEqual(len(list(ov.items_on_page(2))), 1)
        self.assertEqual(len(list(ov.items_on_page(0))), 0)

    def test_place_after_delete_stays_on_current_logical_page(self):
        ov = OverlayDocument(page_count=3)
        plan = PagePlan.identity("/tmp/doc.pdf", 3)
        plan.delete_page(0, overlay=ov)
        asset = SignatureAsset(id="a", name="Bart", kind="image", png_b64=solid_png_b64())
        current = 1
        item = place_signature_on_page(ov, asset, page_index=current, page_w=612, page_h=792)
        self.assertEqual(item.page, current)
        self.assertEqual(item.page, 1)
        self.assertLess(item.page, len(plan))


@unittest.skipIf(fitz is None, "PyMuPDF not installed")
class SignatureExportPixelTests(unittest.TestCase):
    def _pdf(self, path: Path, pages: int = 1) -> None:
        doc = fitz.open()
        for i in range(pages):
            page = doc.new_page(width=200, height=200)
            page.insert_text((20, 40), f"Page {i + 1}", fontsize=12)
        doc.save(path.as_posix())
        doc.close()

    def test_draw_png_survives_flatten_even_with_degenerate_strokes(self):
        from pdf_pro.export import export_pdf

        png = solid_png_b64(40, 16, rgb=(0, 0, 0))
        asset = SignatureAsset(
            id="a",
            name="Bart",
            kind="draw",
            png_b64=png,
            strokes=[[{"x": 0.0, "y": 0.0, "p": 1.0}]],
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.pdf"
            dest = Path(tmp) / "out.pdf"
            self._pdf(src)
            ov = OverlayDocument(source_path=str(src), page_count=1)
            item = place_signature_on_page(ov, asset, page_index=0, page_w=200, page_h=200)
            export_pdf(src, ov, dest)
            out = fitz.open(dest.as_posix())
            pix = out[0].get_pixmap(alpha=False)
            out.close()
            x0 = int(item.x) + 2
            y0 = int(item.y) + 2
            x1 = int(item.x + item.width) - 2
            y1 = int(item.y + item.height) - 2
            dark = 0
            for y in range(max(0, y0), min(pix.height, y1)):
                for x in range(max(0, x0), min(pix.width, x1)):
                    r, g, b = pix.pixel(x, y)
                    if r + g + b < 80:
                        dark += 1
            self.assertGreater(dark, 20, "signature PNG must be visible in the export")

    def test_place_on_page_two_exports_on_page_two(self):
        from pdf_pro.export import export_pdf

        png = solid_png_b64(40, 16, rgb=(0, 0, 0))
        asset = SignatureAsset(id="a", name="Bart", kind="image", png_b64=png)
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.pdf"
            dest = Path(tmp) / "out.pdf"
            self._pdf(src, pages=3)
            ov = OverlayDocument(source_path=str(src), page_count=3)
            place_signature_on_page(ov, asset, page_index=1, page_w=200, page_h=200)
            export_pdf(src, ov, dest)
            out = fitz.open(dest.as_posix())
            self.assertEqual(out.page_count, 3)

            def dark_count(page):
                pix = page.get_pixmap(alpha=False)
                n = 0
                for y in range(pix.height):
                    for x in range(pix.width):
                        r, g, b = pix.pixel(x, y)
                        if r + g + b < 80:
                            n += 1
                return n

            self.assertGreater(dark_count(out[1]), dark_count(out[0]))
            out.close()


if __name__ == "__main__":
    unittest.main()
