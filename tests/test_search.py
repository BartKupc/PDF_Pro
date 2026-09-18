from __future__ import annotations

import unittest

from pdf_pro.search import SearchHit, copy_text_from_hits, search_page_words


class SearchTests(unittest.TestCase):
    def test_finds_word_and_copies_source_text(self):
        words = [
            (72, 70, 120, 86, "Invoice"),
            (125, 70, 170, 86, "100"),
            (72, 100, 140, 116, "Total"),
        ]
        hits = search_page_words(words, "Invoice", 0)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].page, 0)
        self.assertEqual(hits[0].text, "Invoice")
        self.assertEqual(copy_text_from_hits(hits), "Invoice")

    def test_multi_word_window(self):
        words = [
            (10, 10, 40, 20, "cover"),
            (42, 10, 80, 20, "and"),
            (82, 10, 140, 20, "replace"),
        ]
        hits = search_page_words(words, "cover and replace", 2)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].page, 2)
        self.assertIn("cover", hits[0].text)

    def test_empty_query(self):
        self.assertEqual(search_page_words([(0, 0, 1, 1, "a")], "  ", 0), [])

    def test_hit_rect(self):
        hit = SearchHit(0, 1, 2, 3, 4, "x")
        self.assertEqual(hit.rect(), (1, 2, 3, 4))


if __name__ == "__main__":
    unittest.main()
