"""Tests for overlay JSON model — stdlib unittest, no extra deps."""

from __future__ import annotations

import json
import unittest

from pdf_pro.overlay import (
    OverlayDocument,
    OverlayItem,
    make_cover_replace,
    make_image,
    make_signature,
    make_text,
    make_whiteout,
)


class OverlayModelTests(unittest.TestCase):
    def test_round_trip_json(self):
        doc = OverlayDocument(source_path="/tmp/a.pdf", source_sha256="abc", page_count=2)
        doc.add(make_text(0, 10, 20, 100, 24, text="Hello", bold=True, color="#112233"))
        doc.add(make_whiteout(0, 10, 50, 80, 16))
        doc.add(make_cover_replace(1, 5, 5, 60, 18, text="42"))
        doc.add(make_image(1, 0, 0, 40, 20, png_b64="QQ==", aspect_lock=True))
        doc.add(make_signature(1, 100, 200, 120, 40, kind="draw", strokes=[[{"x": 0, "y": 0, "p": 1}]]))
        text = doc.to_json()
        restored = OverlayDocument.from_json(text)
        self.assertEqual(restored.source_sha256, "abc")
        self.assertEqual(len(restored.items), 5)
        self.assertEqual(restored.items[0].data["text"], "Hello")
        self.assertTrue(restored.has_signature())
        self.assertTrue(restored.has_cover_replace())
        json.loads(text)  # valid JSON

    def test_hit_test_topmost(self):
        doc = OverlayDocument(page_count=1)
        a = make_text(0, 0, 0, 50, 50, text="a")
        b = make_text(0, 10, 10, 50, 50, text="b")
        doc.add(a)
        doc.add(b)
        hit = doc.hit_test(0, 15, 15)
        self.assertEqual(hit.id, b.id)

    def test_coordinates_independent_of_zoom(self):
        item = make_text(0, 72, 144, 200, 20, text="x")
        # zoom is a view concern; stored coords stay in PDF points
        self.assertEqual(item.x, 72)
        self.assertEqual(item.y, 144)

    def test_unknown_type_rejected(self):
        with self.assertRaises(ValueError):
            OverlayItem(id="1", type="stamp", page=0, x=0, y=0, width=1, height=1)

    def test_remove(self):
        doc = OverlayDocument()
        t = doc.add(make_text(0, 0, 0, 10, 10))
        self.assertIsNotNone(doc.remove(t.id))
        self.assertIsNone(doc.get(t.id))


if __name__ == "__main__":
    unittest.main()
