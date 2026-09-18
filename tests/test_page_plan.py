"""Page ops: rotate/delete/reorder/duplicate + overlay remapping."""

from __future__ import annotations

import unittest

from pdf_pro.overlay import OverlayDocument, make_text
from pdf_pro.page_plan import PagePlan, PageRef


class PagePlanTests(unittest.TestCase):
    def _doc(self) -> OverlayDocument:
        ov = OverlayDocument(source_path="/tmp/a.pdf", source_sha256="x", page_count=3)
        ov.add(make_text(0, 1, 1, 10, 10, text="p0"))
        ov.add(make_text(1, 2, 2, 10, 10, text="p1"))
        ov.add(make_text(2, 3, 3, 10, 10, text="p2"))
        return ov

    def test_identity_and_json_round_trip(self):
        plan = PagePlan.identity("/tmp/a.pdf", 3)
        self.assertEqual(len(plan.pages), 3)
        self.assertEqual(plan.pages[2].source_index, 2)
        restored = PagePlan.from_dict(plan.to_dict())
        self.assertEqual(restored.pages[1].source_path, "/tmp/a.pdf")
        self.assertEqual(restored.pages[1].source_index, 1)

    def test_rotate_accumulates_mod_360(self):
        plan = PagePlan.identity("/tmp/a.pdf", 1)
        plan.rotate(0, 90)
        plan.rotate(0, 90)
        self.assertEqual(plan.pages[0].rotation, 180)
        plan.rotate(0, 180)
        self.assertEqual(plan.pages[0].rotation, 0)

    def test_delete_remaps_overlays(self):
        ov = self._doc()
        plan = PagePlan.identity("/tmp/a.pdf", 3)
        plan.delete_page(1, overlay=ov)
        self.assertEqual(len(plan.pages), 2)
        texts = [i.data["text"] for i in ov.items]
        self.assertEqual(texts, ["p0", "p2"])
        self.assertEqual(ov.items[1].page, 1)
        self.assertEqual(ov.page_count, 2)

    def test_duplicate_copies_overlays_and_shifts(self):
        ov = self._doc()
        plan = PagePlan.identity("/tmp/a.pdf", 3)
        plan.duplicate_page(0, overlay=ov)
        self.assertEqual(len(plan.pages), 4)
        self.assertEqual(plan.pages[1].source_index, 0)
        pages = {(i.page, i.data["text"]) for i in ov.items}
        self.assertIn((0, "p0"), pages)
        self.assertIn((1, "p0"), pages)
        self.assertEqual([i.data["text"] for i in ov.items if i.page == 2], ["p1"])
        self.assertEqual([i.data["text"] for i in ov.items if i.page == 3], ["p2"])

    def test_reorder_preserves_overlay_binding(self):
        ov = self._doc()
        plan = PagePlan.identity("/tmp/a.pdf", 3)
        plan.reorder([2, 0, 1], overlay=ov)
        self.assertEqual([p.source_index for p in plan.pages], [2, 0, 1])
        by_text = {i.data["text"]: i.page for i in ov.items}
        self.assertEqual(by_text["p2"], 0)
        self.assertEqual(by_text["p0"], 1)
        self.assertEqual(by_text["p1"], 2)

    def test_move_up_down(self):
        ov = self._doc()
        plan = PagePlan.identity("/tmp/a.pdf", 3)
        plan.move_page(2, 0, overlay=ov)
        self.assertEqual([p.source_index for p in plan.pages], [2, 0, 1])

    def test_merge_appends_other_source(self):
        plan = PagePlan.identity("/tmp/a.pdf", 2)
        plan.merge_from("/tmp/b.pdf", page_count=2)
        self.assertEqual(len(plan.pages), 4)
        self.assertEqual(plan.pages[3].source_path, "/tmp/b.pdf")
        self.assertEqual(plan.pages[3].source_index, 1)

    def test_extract_subset(self):
        plan = PagePlan.identity("/tmp/a.pdf", 4)
        sub = plan.extract([1, 3])
        self.assertEqual([p.source_index for p in sub.pages], [1, 3])
        self.assertEqual(len(plan.pages), 4)

    def test_page_ref_round_trip(self):
        ref = PageRef(source_path="x.pdf", source_index=4, rotation=90)
        again = PageRef.from_dict(ref.to_dict())
        self.assertEqual(again.source_index, 4)
        self.assertEqual(again.rotation, 90)


if __name__ == "__main__":
    unittest.main()
