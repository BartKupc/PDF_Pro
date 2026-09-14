"""Preview dialog footer buttons stay outside the scroll area (1366x768)."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_available() -> bool:
    try:
        import PySide6.QtWidgets  # noqa: F401

        return True
    except Exception:
        return False


class PreviewLayoutTests(unittest.TestCase):
    @unittest.skipUnless(_qt_available(), "PySide6 not installed")
    def test_footer_buttons_are_not_inside_scroll(self):
        from PySide6.QtWidgets import QApplication, QScrollArea

        from pdf_pro.ui.preview import PreviewDialog

        app = QApplication.instance() or QApplication([])
        dlg = PreviewDialog.__new__(PreviewDialog)
        from PySide6.QtWidgets import QDialog

        QDialog.__init__(dlg)
        dlg._setup_ui()

        self.assertIsNotNone(dlg.scroll)
        self.assertIsNotNone(dlg.export_btn)
        self.assertIsNotNone(dlg.footer)
        parent = dlg.export_btn.parentWidget()
        while parent is not None:
            self.assertFalse(
                isinstance(parent, QScrollArea),
                "export button is inside a QScrollArea",
            )
            self.assertIsNot(parent, dlg.scroll)
            parent = parent.parentWidget()

        # 1366x768: chrome + dialog chrome leave ~700px usable height
        self.assertLessEqual(dlg.minimumHeight(), 640)
        self.assertTrue(dlg.sizeGripEnabled() or dlg.minimumHeight() <= 640)
        app  # keep app alive for the assertion block

    @unittest.skipUnless(_qt_available(), "PySide6 not installed")
    def test_export_button_object_name(self):
        from PySide6.QtWidgets import QApplication, QDialog

        from pdf_pro.ui.preview import PreviewDialog

        app = QApplication.instance() or QApplication([])
        dlg = PreviewDialog.__new__(PreviewDialog)
        QDialog.__init__(dlg)
        dlg._setup_ui()
        self.assertEqual(dlg.export_btn.text(), "Looks good — choose export location")
        app


if __name__ == "__main__":
    unittest.main()
