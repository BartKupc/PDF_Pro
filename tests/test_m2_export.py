"""M2 export: page ops composition, atomic write, style/shapes round-trip."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

try:
    import fitz
except ImportError:
    fitz = None


@unittest.skipIf(fitz is None, "PyMuPDF not installed")
class M2ExportTests(unittest.TestCase):
    def _pdf(self, path: Path, pages: int = 3, text: str = "Doc") -> None:
        doc = fitz.open()
        for i in range(pages):
            page = doc.new_page(width=200, height=200)
            page.insert_text((20, 40), f"{text} {i + 1}", fontsize=14)
        doc.save(path.as_posix())
        doc.close()

    def test_atomic_partial_cleaned_on_failure(self):
        from pdf_pro.export import ExportError, _atomic_save

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out.pdf"
            partial = dest.with_name(dest.name + ".partial")

            class Boom:
                def save(self, *a, **k):
                    partial.write_bytes(b"partial")
                    raise OSError("disk full")

            with self.assertRaises(ExportError):
                _atomic_save(Boom(), dest)
            self.assertFalse(partial.exists())
            self.assertFalse(dest.exists())

    def test_merge_extract_page_order(self):
        from pdf_pro.compose import write_plan_pdf
        from pdf_pro.page_plan import PagePlan

        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.pdf"
            b = Path(tmp) / "b.pdf"
            self._pdf(a, pages=2, text="A")
            self._pdf(b, pages=2, text="B")
            plan = PagePlan.identity(str(a), 2)
            plan.merge_from(str(b), 2)
            merged = Path(tmp) / "merged.pdf"
            write_plan_pdf(plan, merged)
            doc = fitz.open(merged.as_posix())
            texts = [p.get_text("text") for p in doc]
            doc.close()
            self.assertEqual(len(texts), 4)
            self.assertIn("A 1", texts[0])
            self.assertIn("A 2", texts[1])
            self.assertIn("B 1", texts[2])
            self.assertIn("B 2", texts[3])
            extracted = Path(tmp) / "ex.pdf"
            write_plan_pdf(plan.extract([3, 0]), extracted)
            ex = fitz.open(extracted.as_posix())
            et = [p.get_text("text") for p in ex]
            ex.close()
            self.assertEqual(len(et), 2)
            self.assertIn("B 2", et[0])
            self.assertIn("A 1", et[1])

    def test_page_ops_overlay_on_rotated_composed_page(self):
        from pdf_pro.document import file_sha256
        from pdf_pro.export import export_pdf
        from pdf_pro.overlay import OverlayDocument, make_text, make_whiteout
        from pdf_pro.page_plan import PagePlan

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.pdf"
            self._pdf(src, pages=2, text="Keep")
            before = file_sha256(src)
            plan = PagePlan.identity(str(src), 2)
            plan.rotate(0, 90)
            plan.duplicate_page(0)
            ov = OverlayDocument(source_path=str(src), source_sha256=before, page_count=3)
            ov.add(make_whiteout(0, 10, 10, 40, 30, color="#FFFFFF"))
            ov.add(make_text(1, 10, 10, 80, 24, text="DUP", font_size=16, color="#FF0000"))
            dest = Path(tmp) / "out.pdf"
            export_pdf(src, ov, dest, plan=plan)
            self.assertEqual(file_sha256(src), before)
            out = fitz.open(dest.as_posix())
            self.assertEqual(out.page_count, 3)
            self.assertEqual(int(out[0].rotation) % 360, 90)
            self.assertEqual(int(out[1].rotation) % 360, 90)
            pix = out[1].get_pixmap(alpha=False)
            found = False
            for y in range(pix.height):
                for x in range(pix.width):
                    r, g, b = pix.pixel(x, y)
                    if r > 180 and g < 90 and b < 90:
                        found = True
                        break
                if found:
                    break
            out.close()
            self.assertTrue(found, "overlay on duplicated rotated page missing")

    def test_style_and_shape_export(self):
        from pdf_pro.export import export_pdf
        from pdf_pro.overlay import OverlayDocument, make_shape, make_text

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "s.pdf"
            self._pdf(src, pages=1, text="Base")
            ov = OverlayDocument(source_path=str(src), page_count=1)
            ov.add(
                make_text(
                    0, 10, 60, 120, 24, text="Hi", italic=True, underline=True, align="center", background="#EEEEEE"
                )
            )
            ov.add(make_shape(0, 20, 100, 60, 40, "rect", fill="#000000"))
            dest = Path(tmp) / "s_amended.pdf"
            export_pdf(src, ov, dest)
            self.assertTrue(dest.is_file())
            out = fitz.open(dest.as_posix())
            pix = out[0].get_pixmap(alpha=False)
            r, g, b = pix.pixel(40, 120)
            out.close()
            self.assertLess(r + g + b, 80)

    def test_search_text_layer(self):
        from pdf_pro.search import search_fitz_doc

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "s.pdf"
            self._pdf(src, pages=2, text="Invoice")
            doc = fitz.open(src.as_posix())
            hits = search_fitz_doc(doc, "Invoice")
            doc.close()
            self.assertGreaterEqual(len(hits), 2)
            self.assertEqual(hits[0].text, "Invoice")


if __name__ == "__main__":
    unittest.main()
