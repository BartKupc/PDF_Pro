from __future__ import annotations

import unittest

from pdf_pro.content_scan import (
    MISSING_FONT_NOTICE,
    SCAN_ONLY_NOTICE,
    page_is_scan_only,
    warnings_for_pages,
)


class ContentScanTests(unittest.TestCase):
    def test_scan_only_page_flagged(self):
        self.assertTrue(page_is_scan_only("", image_count=1))
        self.assertTrue(page_is_scan_only("  ", image_count=2))
        self.assertFalse(page_is_scan_only("Selectable invoice text", image_count=1))
        warns = warnings_for_pages([(0, "", 1, [])])
        self.assertEqual(warns[0].kind, "scan")
        self.assertIn("scan", warns[0].message.lower())
        self.assertEqual(warns[0].message, SCAN_ONLY_NOTICE)

    def test_missing_font_notice(self):
        fonts = [(1, "", "Type1", "MissingFont")]
        warns = warnings_for_pages([(0, "Hello world text", 0, fonts)])
        self.assertTrue(any(w.kind == "font" for w in warns))
        self.assertIn("MissingFont", warns[0].message)
        self.assertIn("not embedded", MISSING_FONT_NOTICE.lower())


if __name__ == "__main__":
    unittest.main()
