"""Offscreen QImage → PNG helper and draw-pad Use-on-page.

These tests execute real QImage.save via Qt (CI: QT_QPA_PLATFORM=offscreen).
They must fail on v0.2.2 (BytesIO passed to QImage.save) and pass after the
QBuffer helper lands.
"""

from __future__ import annotations

import base64
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_and_fitz() -> bool:
    try:
        import PySide6.QtWidgets  # noqa: F401
        import fitz  # noqa: F401

        return True
    except Exception:
        return False


def _write_pdf(path: Path) -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Sign here", fontsize=14)
    doc.save(path.as_posix())
    doc.close()


@unittest.skipUnless(_qt_and_fitz(), "PySide6/PyMuPDF not installed")
class QImagePngHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_qimage_to_png_bytes_roundtrip(self) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QImage, QPainter, QPen

        from pdf_pro.ui.qt_image import qimage_to_png_bytes

        img = QImage(64, 32, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        painter = QPainter(img)
        painter.setPen(QPen(QColor("black"), 3))
        painter.drawLine(2, 16, 62, 16)
        painter.end()

        png = qimage_to_png_bytes(img)
        self.assertTrue(png, "PNG bytes must be non-empty")
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"), "must be a PNG")

        back = QImage()
        self.assertTrue(back.loadFromData(png, "PNG"))
        self.assertEqual(back.width(), img.width())
        self.assertEqual(back.height(), img.height())

    def test_null_qimage_raises(self) -> None:
        from PySide6.QtGui import QImage

        from pdf_pro.ui.qt_image import qimage_to_png_bytes

        with self.assertRaises((ValueError, RuntimeError, TypeError)):
            qimage_to_png_bytes(QImage())


@unittest.skipUnless(_qt_and_fitz(), "PySide6/PyMuPDF not installed")
class DrawPadUseOnPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_draw_use_on_page_places_overlay_with_png(self) -> None:
        from unittest import mock

        from PySide6.QtWidgets import QDialog, QPushButton

        from pdf_pro.ui.main_window import MainWindow
        from pdf_pro.ui.signature_studio import SignatureStudio

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.pdf"
            _write_pdf(src)
            win = MainWindow()
            try:
                win.open_path(src)
                self.assertIsNotNone(win.pane())
                self.assertIsNotNone(win.pane().session.opened)

                def auto_exec(dlg):
                    dlg.tabs.setCurrentIndex(0)
                    dlg.pad.setFixedSize(420, 180)
                    dlg.pad.strokes = [
                        [
                            {"x": 0.1, "y": 0.5, "p": 1.0},
                            {"x": 0.9, "y": 0.5, "p": 1.0},
                        ]
                    ]
                    btn = dlg.findChild(QPushButton, "primaryAction")
                    self.assertIsNotNone(btn, "Use on page button missing")
                    btn.click()
                    return QDialog.DialogCode.Accepted

                with mock.patch.object(SignatureStudio, "exec", auto_exec):
                    win._signature(0)

                p = win.pane()
                sigs = [i for i in p.session.overlay.items if i.type == "signature"]
                self.assertEqual(len(sigs), 1, "Use on page must add a signature overlay")
                png_b64 = (sigs[0].data or {}).get("png_b64") or ""
                self.assertTrue(png_b64.strip(), "placed signature must carry PNG data")
                raw = base64.b64decode(png_b64)
                self.assertTrue(raw.startswith(b"\x89PNG\r\n\x1a\n"))
            finally:
                win.close()


class NoBytesIOQImageSaveTests(unittest.TestCase):
    """Catches the v0.2.2 PIL-style QImage.save(BytesIO) leak without Qt."""

    def test_ui_does_not_save_qimage_to_bytesio(self) -> None:
        root = Path(__file__).resolve().parents[1] / "pdf_pro"
        offenders: list[str] = []
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "BytesIO(" in text:
                offenders.append(str(path.relative_to(root.parent)))
        self.assertEqual(
            offenders,
            [],
            "QImage.save does not accept BytesIO; use qimage_to_png_bytes",
        )

    def test_helper_is_used_at_all_encode_sites(self) -> None:
        root = Path(__file__).resolve().parents[1]
        studio = (root / "pdf_pro" / "ui" / "signature_studio.py").read_text(encoding="utf-8")
        main = (root / "pdf_pro" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("qimage_to_png_bytes", studio)
        self.assertEqual(studio.count("qimage_to_png_bytes("), 3)
        self.assertIn("qimage_to_png_bytes", main)
        self.assertGreaterEqual(main.count("qimage_to_png_bytes("), 1)


if __name__ == "__main__":
    unittest.main()

