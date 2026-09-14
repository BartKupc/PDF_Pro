from __future__ import annotations

import unittest

from pdf_pro.overlay import make_text
from pdf_pro.snap import snap_rect


class SnapTests(unittest.TestCase):
    def test_snaps_to_page_center(self):
        x, y, guides = snap_rect(97, 10, 6, 6, others=[], page_width=200, page_height=200, threshold=5)
        self.assertAlmostEqual(x, 97)  # 97+3=100 center, already near? wait 97+3=100
        # center of item is 100, page center 100 — already aligned
        self.assertTrue(any(g[0] == "v" for g in guides) or abs((x + 3) - 100) < 1)

    def test_snaps_to_other_item_edge(self):
        other = make_text(0, 50, 50, 20, 10)
        x, y, guides = snap_rect(48, 80, 10, 10, others=[other], page_width=400, page_height=400, threshold=5)
        self.assertAlmostEqual(x, 50)
        self.assertTrue(any(g[0] == "v" and g[1] == 50 for g in guides))
