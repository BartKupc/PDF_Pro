"""PDF integration tests. Skipped when PyMuPDF is not installed."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

try:
    import fitz
except ImportError:
    fitz = None


@unittest.skipIf(fitz is None, "PyMuPDF not installed")
class PdfIntegrationTests(unittest.TestCase):
    def _make_pdf(self, path: Path, pages: int = 3, text: str = "Invoice 100") -> None:
        doc = fitz.open()
        for i in range(pages):
            page = doc.new_page(width=612, height=792)
            page.insert_text((72, 72 + i), f"{text} page {i + 1}", fontsize=14)
        doc.save(path.as_posix())
        doc.close()

    def test_open_checksum_unchanged(self):
        from pdf_pro.document import file_sha256, open_pdf, verify_source_untouched

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "doc.pdf"
            self._make_pdf(p, pages=5)
            before = file_sha256(p)
            opened = open_pdf(p)
            pix = opened.render_pixmap(0, scale=1.0)
            self.assertGreater(pix.width, 10)
            opened.close()
            self.assertTrue(verify_source_untouched(p, before))
            self.assertEqual(file_sha256(p), before)

    def test_password_prompt_contract(self):
        from pdf_pro.document import NeedsPassword, WrongPassword, open_pdf

        with tempfile.TemporaryDirectory() as tmp:
            plain = Path(tmp) / "plain.pdf"
            p = Path(tmp) / "enc.pdf"
            self._make_pdf(plain)
            doc = fitz.open(plain.as_posix())
            # PyMuPDF refuses non-incremental save back to the opened path.
            doc.save(
                p.as_posix(),
                encryption=fitz.PDF_ENCRYPT_AES_256,
                user_pw="secret",
                owner_pw="owner",
            )
            doc.close()
            with self.assertRaises(NeedsPassword):
                open_pdf(p)
            with self.assertRaises(WrongPassword):
                open_pdf(p, password="nope")
            opened = open_pdf(p, password="secret")
            self.assertTrue(opened.encrypted)
            opened.close()

    def test_export_cover_and_signature_new_file(self):
        from pdf_pro.document import file_sha256, open_pdf
        from pdf_pro.export import default_export_path, export_pdf
        from pdf_pro.overlay import OverlayDocument, make_cover_replace, make_signature

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "business.pdf"
            self._make_pdf(p, pages=2, text="Amount 99.00")
            before = file_sha256(p)
            ov = OverlayDocument(source_path=str(p), source_sha256=before, page_count=2)
            ov.add(make_cover_replace(0, 70, 60, 120, 20, text="Amount 12.00"))
            ov.add(make_signature(1, 400, 700, 120, 40, kind="type", text="Bart", font_family="Dancing Script"))
            dest = default_export_path(p, ov)
            self.assertTrue(str(dest).endswith("_signed.pdf"))
            export_pdf(p, ov, dest)
            self.assertEqual(file_sha256(p), before)
            self.assertTrue(dest.is_file())
            out = open_pdf(dest)
            self.assertEqual(out.page_count, 2)
            out.close()

    def test_export_unwritable_errors(self):
        from pdf_pro.export import ExportError, export_pdf
        from pdf_pro.overlay import OverlayDocument

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.pdf"
            self._make_pdf(p)
            ov = OverlayDocument(page_count=1)
            dest = Path("/proc/pdf_pro_cannot_write.pdf")
            with self.assertRaises(ExportError):
                export_pdf(p, ov, dest)

    def test_detect_signature_field(self):
        from pdf_pro.document import detect_digital_signature, open_pdf

        with tempfile.TemporaryDirectory() as tmp:
            created = Path(tmp) / "created.pdf"
            p = Path(tmp) / "signed.pdf"
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 72), "signed", fontsize=12)
            widget = fitz.Widget()
            widget.field_name = "Signature1"
            widget.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE
            widget.rect = fitz.Rect(72, 400, 200, 460)
            page.add_widget(widget)
            doc.save(created.as_posix())
            doc.close()
            raw = created.read_bytes()
            self.assertTrue(
                b"/FT /Sig" in raw or b"/Type /Sig" in raw or b"/Sig" in raw,
                "signature widget did not persist in the fixture PDF",
            )
            created.replace(p)
            opened = open_pdf(p)
            self.assertTrue(detect_digital_signature(opened.fitz_doc))
            self.assertTrue(opened.has_digital_signature)
            opened.close()

    def test_refuse_overwrite_source(self):
        from pdf_pro.export import ExportError, export_pdf
        from pdf_pro.overlay import OverlayDocument

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.pdf"
            self._make_pdf(p)
            ov = OverlayDocument(page_count=1)
            with self.assertRaises(ExportError):
                export_pdf(p, ov, p)

    def test_export_overlay_on_rotated_page_lands_in_visual_place(self):
        """Overlays are authored in get_pixmap/page.rect space; export must derotate."""
        from pdf_pro.document import file_sha256
        from pdf_pro.export import export_pdf
        from pdf_pro.overlay import OverlayDocument, make_text, make_whiteout

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "rotated.pdf"
            doc = fitz.open()
            page = doc.new_page(width=200, height=100)
            page.draw_rect(page.rect, color=(0, 0, 0), fill=(0, 0, 0), width=0)
            page.set_rotation(90)
            doc.save(p.as_posix())
            doc.close()

            vis = fitz.open(p.as_posix())
            vpage = vis[0]
            vis_w, vis_h = float(vpage.rect.width), float(vpage.rect.height)
            vis.close()
            self.assertAlmostEqual(vis_w, 100)
            self.assertAlmostEqual(vis_h, 200)

            before = file_sha256(p)
            ov = OverlayDocument(source_path=str(p), source_sha256=before, page_count=1)
            # Visual-space white-out near the displayed top-left.
            ov.add(make_whiteout(0, 10, 10, 40, 30, color="#FFFFFF"))
            # Visual-space red text; exercises derotate-rect + rotate=page.rotation.
            ov.add(make_text(0, 10, 80, 80, 40, text="X", font_size=28, color="#FF0000"))
            dest = Path(tmp) / "rotated_amended.pdf"
            export_pdf(p, ov, dest)
            self.assertEqual(file_sha256(p), before)

            out = fitz.open(dest.as_posix())
            pix = out[0].get_pixmap(alpha=False)
            out.close()
            # Pixmap matches visual page at scale 1.
            self.assertEqual(pix.width, 100)
            self.assertEqual(pix.height, 200)
            r, g, b = pix.pixel(30, 25)
            self.assertGreater(r, 200)
            self.assertGreater(g, 200)
            self.assertGreater(b, 200)
            r2, g2, b2 = pix.pixel(80, 180)
            self.assertLess(r2, 40)
            self.assertLess(g2, 40)
            self.assertLess(b2, 40)
            found_red = False
            for y in range(80, 120):
                for x in range(10, 90):
                    rr, gg, bb = pix.pixel(x, y)
                    if rr > 180 and gg < 80 and bb < 80:
                        found_red = True
                        break
                if found_red:
                    break
            self.assertTrue(
                found_red,
                "text overlay not visible in visual-space box on rotated page",
            )


if __name__ == "__main__":
    unittest.main()
