from __future__ import annotations

import unittest

from pdf_pro.overlay import OverlayDocument, make_image, make_shape, make_signature, make_text
from pdf_pro.overlay_ops import bring_to_front, duplicate_item, rotate_item, send_to_back, z_index


class OverlayOpsTests(unittest.TestCase):
    def test_style_round_trip_json(self):
        doc = OverlayDocument(page_count=1)
        doc.add(
            make_text(
                0,
                0,
                0,
                80,
                20,
                text="Hi",
                italic=True,
                underline=True,
                align="center",
                background="#FFFF00",
                opacity=0.5,
            )
        )
        doc.add(make_shape(0, 10, 10, 40, 20, "rect", fill="#000000"))
        restored = OverlayDocument.from_json(doc.to_json())
        t = restored.items[0]
        self.assertTrue(t.data["italic"])
        self.assertTrue(t.data["underline"])
        self.assertEqual(t.data["align"], "center")
        self.assertEqual(t.data["background"], "#FFFF00")
        self.assertEqual(t.data["opacity"], 0.5)
        self.assertEqual(restored.items[1].data["kind"], "rect")

    def test_duplicate_and_rotate_image_and_signature(self):
        doc = OverlayDocument(page_count=1)
        img = doc.add(make_image(0, 5, 5, 40, 20, png_b64="QQ=="))
        sig = doc.add(make_signature(0, 8, 8, 60, 20, kind="type", text="Bart", date="2026-01-01", label="Bart K"))
        dup = duplicate_item(doc, img.id)
        self.assertNotEqual(dup.id, img.id)
        self.assertEqual(dup.x, img.x + 12)
        rotate_item(img, 90)
        self.assertEqual(img.rotation, 90)
        self.assertAlmostEqual(img.width, 20)
        self.assertAlmostEqual(img.height, 40)
        rotate_item(sig, 90)
        self.assertEqual(sig.rotation, 90)
        self.assertEqual(sig.data["date"], "2026-01-01")

    def test_layer_order(self):
        doc = OverlayDocument(page_count=1)
        a = doc.add(make_text(0, 0, 0, 10, 10, text="a"))
        b = doc.add(make_text(0, 0, 0, 10, 10, text="b"))
        self.assertEqual(z_index(doc, a.id), 0)
        bring_to_front(doc, a.id)
        self.assertEqual(doc.items[-1].id, a.id)
        send_to_back(doc, b.id)
        self.assertEqual(doc.items[0].id, b.id)

    def test_unknown_shape_rejected(self):
        with self.assertRaises(ValueError):
            make_shape(0, 0, 0, 1, 1, "stamp")


if __name__ == "__main__":
    unittest.main()
