from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pdf_pro.kdf import derive_key


class KdfTests(unittest.TestCase):
    def test_argon2id_deterministic(self):
        salt = b"0123456789abcdef"
        a = derive_key("passphrase", salt)
        b = derive_key("passphrase", salt)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 32)
        self.assertNotEqual(a, derive_key("other", salt))

    def test_empty_rejected(self):
        with self.assertRaises(Exception):
            derive_key("", b"0123456789abcdef")
