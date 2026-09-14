"""Overlay coords live in visual (rotation-applied) space; export needs PDF space."""

from __future__ import annotations

import unittest

from pdf_pro.page_coords import derotate_rect, derotate_xy, overlay_rect


class _Rect:
    def __init__(self, width, height):
        self.width = width
        self.height = height


class _Item:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class _Page:
    def __init__(self, rotation, vis_w, vis_h):
        self.rotation = rotation
        self.rect = _Rect(vis_w, vis_h)


class PageCoordTests(unittest.TestCase):
    def test_rotation_0_is_identity(self):
        self.assertEqual(derotate_xy(10, 20, 0, 612, 792), (10, 20))
        self.assertEqual(derotate_rect(10, 20, 30, 40, 0, 612, 792), (10, 20, 30, 40))

    def test_rot90_visual_origin_maps_to_unrotated_bottom_left(self):
        # Unrotated 612x792, visual 792x612
        x, y = derotate_xy(0, 0, 90, 792, 612)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 792)

    def test_rot90_visual_top_right_maps_to_unrotated_origin(self):
        x, y = derotate_xy(792, 0, 90, 792, 612)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 0)

    def test_rot180_origin_maps_to_opposite_corner(self):
        x, y = derotate_xy(0, 0, 180, 612, 792)
        self.assertAlmostEqual(x, 612)
        self.assertAlmostEqual(y, 792)

    def test_rot270_visual_origin_maps_to_unrotated_top_right(self):
        # Unrotated 612x792, visual 792x612
        x, y = derotate_xy(0, 0, 270, 792, 612)
        self.assertAlmostEqual(x, 612)
        self.assertAlmostEqual(y, 0)

    def test_rot90_axis_aligned_rect_stays_axis_aligned(self):
        x, y, w, h = derotate_rect(10, 20, 40, 30, 90, 792, 612)
        self.assertAlmostEqual(w, 30)
        self.assertAlmostEqual(h, 40)
        self.assertAlmostEqual(x, 20)
        self.assertAlmostEqual(y, 792 - 10 - 40)

    def test_overlay_rect_uses_page_rotation(self):
        page = _Page(90, 792, 612)
        item = _Item(10, 20, 40, 30)
        x0, y0, x1, y1 = overlay_rect(page, item)
        self.assertAlmostEqual(x1 - x0, 30)
        self.assertAlmostEqual(y1 - y0, 40)
        self.assertNotAlmostEqual(x0, 10)
        self.assertNotAlmostEqual(y0, 20)


if __name__ == "__main__":
    unittest.main()
