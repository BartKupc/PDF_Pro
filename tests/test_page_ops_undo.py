"""Regression: page-plan mutations must undo together with overlays."""

from __future__ import annotations

import unittest

from pdf_pro.overlay import make_text
from pdf_pro.session import DocumentSession


class PageOpsUndoTests(unittest.TestCase):
    def test_undo_delete_with_items_restores_plan_and_overlay(self):
        sess = DocumentSession(source_path="/tmp/a.pdf", source_sha256="x", page_count=3)
        sess.overlay.add(make_text(2, 3, 3, 10, 10, text="on-page-3"))
        sess.undo.checkpoint()
        sess.plan.delete_page(0, overlay=sess.overlay)

        self.assertEqual(len(sess.plan), 2)
        self.assertEqual(sess.overlay.items[0].page, 1)

        self.assertTrue(sess.undo.undo())
        self.assertEqual(len(sess.plan), 3)
        self.assertEqual(len(sess.overlay.items), 1)
        self.assertEqual(sess.overlay.items[0].page, 2)
        self.assertEqual(sess.overlay.items[0].data["text"], "on-page-3")
        self.assertLess(sess.overlay.items[0].page, len(sess.plan))
        self.assertEqual(sess.overlay.page_count, 3)

    def test_page_delete_without_items_is_undoable(self):
        sess = DocumentSession(source_path="/tmp/a.pdf", source_sha256="x", page_count=2)
        sess.undo.checkpoint()
        sess.plan.delete_page(0, overlay=sess.overlay)
        self.assertFalse(sess.undo.discard_if_unchanged())
        self.assertTrue(sess.undo.undo())
        self.assertEqual(len(sess.plan), 2)

    def test_page_rotate_is_undoable(self):
        sess = DocumentSession(source_path="/tmp/a.pdf", source_sha256="x", page_count=1)
        sess.undo.checkpoint()
        sess.plan.rotate(0, 90)
        self.assertFalse(sess.undo.discard_if_unchanged())
        self.assertTrue(sess.undo.undo())
        self.assertEqual(sess.plan.pages[0].rotation, 0)


if __name__ == "__main__":
    unittest.main()
