from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pdf_pro.vault import SignatureAsset, SignatureVault, WrongPassphrase, pack_vault, unpack_vault
from pdf_pro.constants import VAULT_MAGIC


class VaultTests(unittest.TestCase):
    def _vault(self, tmp: str) -> SignatureVault:
        return SignatureVault(path=Path(tmp) / "vault.bin")

    def test_first_use_set_and_unlock(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = self._vault(tmp)
            self.assertTrue(v.is_first_use())
            v.set_passphrase("correct horse")
            self.assertTrue(v.unlocked)
            v.add(SignatureAsset(id="s1", name="Bart", kind="draw", png_b64="QUFBQQ=="))
            v.lock()
            self.assertFalse(v.unlocked)
            v2 = self._vault(tmp)
            v2.unlock("correct horse")
            assets = v2.list_assets()
            self.assertEqual(len(assets), 1)
            self.assertEqual(assets[0].name, "Bart")

    def test_wrong_passphrase_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = self._vault(tmp)
            v.set_passphrase("right")
            v.add(SignatureAsset(id="s1", name="secret", kind="image", png_b64="c2VjcmV0cG5n"))
            v.lock()
            v2 = self._vault(tmp)
            with self.assertRaises(WrongPassphrase) as ctx:
                v2.unlock("wrong")
            self.assertIn("Wrong passphrase", str(ctx.exception))
            self.assertFalse(v2.unlocked)

    def test_disk_is_ciphertext(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = self._vault(tmp)
            marker = "UNIQUE_SIGNATURE_PIXELS_XYZ"
            v.set_passphrase("pw")
            v.add(SignatureAsset(id="s1", name="n", kind="image", png_b64=marker))
            raw = v.path.read_bytes()
            self.assertTrue(raw.startswith(VAULT_MAGIC))
            self.assertNotIn(marker.encode(), raw)
            self.assertNotIn(b"UNIQUE_SIGNATURE", raw)
            self.assertTrue(v.disk_is_ciphertext())
            # passphrase never written
            self.assertNotIn(b"pw", raw)

    def test_pack_roundtrip_header(self):
        salt = b"0123456789abcdef"
        body = b"\x00" * 40
        packed = pack_vault(salt, body)
        ver, s2, rest = unpack_vault(packed)
        self.assertEqual(s2, salt)
        self.assertEqual(rest, body)
        self.assertEqual(ver, 1)

    def test_rename_replace_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = self._vault(tmp)
            v.set_passphrase("pw")
            v.add(SignatureAsset(id="s1", name="old", kind="draw", png_b64="QQ=="))
            v.rename("s1", "new-name")
            self.assertEqual(v.get("s1").name, "new-name")
            v.replace("s1", SignatureAsset(id="ignore", name="replaced", kind="type", text="BK"))
            self.assertEqual(v.get("s1").text, "BK")
            self.assertEqual(v.get("s1").id, "s1")
            v.remove("s1")
            self.assertIsNone(v.get("s1"))
