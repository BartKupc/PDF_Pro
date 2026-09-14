"""PyInstaller must ship argon2-cffi; ubuntu-22.04 OpenSSL has no ARGON2ID."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PackagingSpecTests(unittest.TestCase):
    def test_hiddenimports_include_argon2(self):
        text = (ROOT / "PDF_Pro.spec").read_text(encoding="utf-8")
        self.assertIn('"argon2"', text)
        self.assertIn('"argon2.low_level"', text)


if __name__ == "__main__":
    unittest.main()
