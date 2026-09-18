"""Preview accept + export gate must not raise AttributeError on instance.Accepted.

Runs in CI with QT_QPA_PLATFORM=offscreen and real PySide6/PyMuPDF.
Skipped in the sandbox when those packages are missing.
"""

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


def _write_pdf(path: Path, text: str = "Invoice 100") -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), text, fontsize=14)
    doc.save(path.as_posix())
    doc.close()


@unittest.skipUnless(_qt_and_fitz(), "PySide6/PyMuPDF not installed")
class PreviewAcceptGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_accept_button_sets_ok_and_gate_does_not_raise(self):
        from PySide6.QtWidgets import QDialog

        from pdf_pro.overlay import OverlayDocument
        from pdf_pro.ui.preview import PreviewDialog

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.pdf"
            _write_pdf(src)
            overlay = OverlayDocument(source_path=str(src), page_count=1)
            dlg = PreviewDialog(src, overlay, None)
            self.assertTrue(dlg.export_btn.isEnabled())
            dlg.export_btn.click()
            self.assertTrue(dlg.ok)
            code = dlg.result()
            # Export-flow gate (class-scoped). Must not touch dlg.Accepted.
            try:
                rejected = code != QDialog.DialogCode.Accepted or not dlg.ok
            except AttributeError as exc:
                self.fail(f"export-flow gate raised AttributeError: {exc}")
            self.assertFalse(rejected)
            self.assertEqual(code, QDialog.DialogCode.Accepted)


@unittest.skipUnless(_qt_and_fitz(), "PySide6/PyMuPDF not installed")
class ExportFlowAcceptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_accept_preview_mocked_save_writes_export(self):
        from PySide6.QtWidgets import QDialog, QMessageBox

        from pdf_pro.ui.main_window import MainWindow
        from pdf_pro.ui.preview import PreviewDialog

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.pdf"
            dest = Path(tmp) / "out.pdf"
            _write_pdf(src)
            win = MainWindow()
            try:
                win.open_path(src)
                self.assertIsNotNone(win.opened)

                def auto_exec(dlg):
                    dlg.export_btn.click()
                    return QDialog.DialogCode.Accepted

                with mock.patch.object(PreviewDialog, "exec", auto_exec), mock.patch(
                    "pdf_pro.ui.main_window.get_save_file_name",
                    return_value=(str(dest), "PDF files (*.pdf)"),
                ), mock.patch.object(QMessageBox, "exec", lambda box: 0):
                    win.export_flow()
                self.assertTrue(dest.is_file(), "complete_export must write the dest PDF")
                self.assertGreater(dest.stat().st_size, 8)
            finally:
                win.close()


if __name__ == "__main__":
    unittest.main()
