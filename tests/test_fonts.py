from __future__ import annotations

import unittest

from pdf_pro.fonts import BUNDLED_FAMILIES, HANDWRITING_FAMILY, font_path


class FontTests(unittest.TestCase):
    def test_bundled_files_exist(self):
        for family in BUNDLED_FAMILIES:
            path = font_path(family)
            self.assertTrue(path.is_file(), msg=str(path))
        self.assertTrue(font_path(HANDWRITING_FAMILY).is_file())
        self.assertTrue(font_path("DejaVu Sans", bold=True).is_file())
