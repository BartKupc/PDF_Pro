from __future__ import annotations

import unittest

from pdf_pro.overlay import make_text
from pdf_pro.session import DocumentSession


class SessionIsolationTests(unittest.TestCase):
    def test_two_docs_edits_isolated(self):
        a = DocumentSession(source_path="/a.pdf", source_sha256="a", page_count=1)
        b = DocumentSession(source_path="/b.pdf", source_sha256="b", page_count=2)
        a.undo.checkpoint()
        a.overlay.add(make_text(0, 0, 0, 10, 10, text="only-a"))
        a.mark_dirty()
        self.assertEqual(len(a.overlay.items), 1)
        self.assertEqual(len(b.overlay.items), 0)
        self.assertTrue(a.dirty)
        self.assertFalse(b.dirty)
        self.assertIsNot(a.undo, b.undo)
        a.undo.undo()
        self.assertEqual(len(a.overlay.items), 0)
        b.undo.checkpoint()
        b.overlay.add(make_text(0, 1, 1, 10, 10, text="only-b"))
        self.assertEqual(b.overlay.items[0].data["text"], "only-b")
        self.assertEqual(len(a.overlay.items), 0)


if __name__ == "__main__":
    unittest.main()
