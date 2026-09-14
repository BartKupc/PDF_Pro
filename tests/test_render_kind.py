"""Render results must be tagged by kind, never guessed from zoom scale."""

from __future__ import annotations

import unittest

from pdf_pro.constants import MIN_ZOOM
from pdf_pro.render_kind import KIND_PAGE, KIND_THUMB, destination


class RenderKindTests(unittest.TestCase):
    def test_page_render_at_min_zoom_is_not_thumbnail(self):
        self.assertEqual(destination(KIND_PAGE, MIN_ZOOM), "page")
        self.assertEqual(destination(KIND_PAGE, 0.25), "page")
        self.assertEqual(destination(KIND_PAGE, 0.4), "page")

    def test_thumb_kind_is_thumbnail_regardless_of_scale(self):
        self.assertEqual(destination(KIND_THUMB, 0.2), "thumbnail")
        self.assertEqual(destination(KIND_THUMB, 1.25), "thumbnail")

    def test_missing_kind_does_not_treat_min_zoom_as_thumbnail(self):
        self.assertEqual(destination("", 0.25), "page")
        self.assertEqual(destination(None, 0.25), "page")


if __name__ == "__main__":
    unittest.main()
