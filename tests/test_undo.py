from __future__ import annotations

import unittest

from pdf_pro.overlay import OverlayDocument, make_text, make_whiteout
from pdf_pro.undo import UndoStack


class UndoTests(unittest.TestCase):
    def test_twenty_mixed_ops_undo_redo(self):
        doc = OverlayDocument(page_count=1)
        hist = UndoStack(doc)
        ids = []
        for i in range(20):
            hist.checkpoint()
            if i % 2 == 0:
                item = make_text(0, i, i, 40, 12, text=str(i))
            else:
                item = make_whiteout(0, i, i + 10, 30, 10)
            doc.add(item)
            ids.append(item.id)
        self.assertEqual(len(doc.items), 20)
        for _ in range(20):
            self.assertTrue(hist.undo())
        self.assertEqual(len(doc.items), 0)
        for _ in range(20):
            self.assertTrue(hist.redo())
        self.assertEqual(len(doc.items), 20)
        self.assertEqual([i.id for i in doc.items], ids)

    def test_close_clears_history(self):
        doc = OverlayDocument()
        hist = UndoStack(doc)
        hist.checkpoint()
        doc.add(make_text(0, 0, 0, 10, 10))
        hist.close_document()
        self.assertFalse(hist.can_undo())
        self.assertFalse(hist.can_redo())
        self.assertFalse(hist.undo())

    def test_checkpoint_clears_redo(self):
        doc = OverlayDocument()
        hist = UndoStack(doc)
        hist.checkpoint()
        doc.add(make_text(0, 0, 0, 10, 10, text="a"))
        hist.undo()
        self.assertTrue(hist.can_redo())
        hist.checkpoint()
        doc.add(make_text(0, 1, 1, 10, 10, text="b"))
        self.assertFalse(hist.can_redo())
