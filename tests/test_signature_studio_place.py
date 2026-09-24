"""Offscreen SignatureStudio → canvas → flatten. Skipped without PySide6/PyMuPDF."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_and_fitz() -> bool:
    try:
        import PySide6.QtWidgets  # noqa: F401
        import fitz  # noqa: F401

        return True
    except Exception:
        return False


def _write_pdf(path: Path, pages: int = 1, text: str = "Invoice 100") -> None:
    import fitz

    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 72), f"{text} page {i + 1}", fontsize=14)
    doc.save(path.as_posix())
    doc.close()


@unittest.skipUnless(_qt_and_fitz(), "PySide6/PyMuPDF not installed")
class SignatureStudioPlaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _open(self, win, src: Path):
        win.open_path(src)
        self.assertIsNotNone(win.pane())
        self.assertIsNotNone(win.pane().session.opened)

    def test_type_use_on_page_appears_on_canvas_and_export(self):
        from PySide6.QtWidgets import QDialog

        from pdf_pro.ui.main_window import MainWindow
        from pdf_pro.ui.signature_studio import SignatureStudio
        from pdf_pro.export import export_pdf

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.pdf"
            dest = Path(tmp) / "out.pdf"
            _write_pdf(src, pages=1)
            win = MainWindow()
            try:
                self._open(win, src)

                def auto_exec(dlg):
                    dlg.tabs.setCurrentIndex(1)
                    dlg.type_name.setText("BartK")
                    dlg._use()
                    return QDialog.DialogCode.Accepted

                with mock.patch.object(SignatureStudio, "exec", auto_exec):
                    win._signature(1)

                p = win.pane()
                sigs = [i for i in p.session.overlay.items if i.type == "signature"]
                self.assertEqual(len(sigs), 1, "Use on page must add a signature overlay")
                item = sigs[0]
                self.assertEqual(item.page, p.session.current_page)
                self.assertIn(item.id, p.canvas._graphics)
                g = p.canvas._graphics[item.id]
                self.assertTrue(g.isSelected(), "placed signature must be selected so it is visible")
                export_pdf(
                    p.session.opened.path,
                    p.session.overlay,
                    dest,
                    plan=p.session.plan,
                )
                self.assertTrue(dest.is_file())
                import fitz

                out = fitz.open(dest.as_posix())
                pix = out[0].get_pixmap(alpha=False)
                out.close()
                dark = 0
                for y in range(pix.height):
                    for x in range(pix.width):
                        r, g, b = pix.pixel(x, y)
                        if r + g + b < 200:
                            dark += 1
                self.assertGreater(dark, 10, "typed signature must appear in flattened export")
            finally:
                win.close()

    def test_place_on_page_two_with_second_tab_open(self):
        from PySide6.QtWidgets import QDialog

        from pdf_pro.ui.main_window import MainWindow
        from pdf_pro.ui.signature_studio import SignatureStudio

        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.pdf"
            b = Path(tmp) / "b.pdf"
            _write_pdf(a, pages=3, text="AAA")
            _write_pdf(b, pages=2, text="BBB")
            win = MainWindow()
            try:
                self._open(win, a)
                self._open(win, b)
                win.tabs.setCurrentIndex(0)
                win.goto_page(1)
                p_a = win.pane()
                self.assertEqual(p_a.session.opened.path.name, "a.pdf")
                self.assertEqual(p_a.session.current_page, 1)

                def auto_exec(dlg):
                    dlg.tabs.setCurrentIndex(1)
                    dlg.type_name.setText("OnPage2")
                    dlg._use()
                    return QDialog.DialogCode.Accepted

                with mock.patch.object(SignatureStudio, "exec", auto_exec):
                    win._signature(1)

                p_a = win.pane()
                sigs = [i for i in p_a.session.overlay.items if i.type == "signature"]
                self.assertEqual(len(sigs), 1)
                self.assertEqual(sigs[0].page, 1)
                pane_b = win.tabs.widget(1)
                self.assertEqual(len(pane_b.session.overlay.items), 0)
            finally:
                win.close()

    def test_studio_has_no_passphrase_prompt_on_plain_vault(self):
        from pdf_pro.ui.signature_studio import SignatureStudio
        from pdf_pro.vault import SignatureVault

        with tempfile.TemporaryDirectory() as tmp:
            vault = SignatureVault(path=Path(tmp) / "vault.json")
            dlg = SignatureStudio(vault)
            self.assertFalse(dlg.pass_edit.isVisible())
            self.assertFalse(dlg.migrate_btn.isVisible())
            self.assertNotIn("passphrase", dlg.vault_status.text().lower())


if __name__ == "__main__":
    unittest.main()
