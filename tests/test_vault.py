"""Plain signature vault + one-time migration from the encrypted v0.2.1 format."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pdf_pro.constants import VAULT_MAGIC
from pdf_pro.vault import (
    SignatureAsset,
    SignatureVault,
    VaultError,
    WrongPassphrase,
    is_encrypted_vault_bytes,
    write_legacy_encrypted_vault,
)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401

    HAS_CRYPTO = True
except Exception:
    HAS_CRYPTO = False


class PlainVaultTests(unittest.TestCase):
    def _vault(self, tmp: str) -> SignatureVault:
        return SignatureVault(path=Path(tmp) / "vault.json")

    def test_plain_save_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = self._vault(tmp)
            self.assertTrue(v.unlocked)
            self.assertFalse(v.needs_migration)
            v.add(SignatureAsset(id="s1", name="Bart", kind="draw", png_b64="QUFBQQ=="))
            raw = v.path.read_text(encoding="utf-8")
            self.assertIn("Bart", raw)
            self.assertIn("QUFBQQ==", raw)
            self.assertFalse(v.path.read_bytes().startswith(VAULT_MAGIC))
            v2 = self._vault(tmp)
            assets = v2.list_assets()
            self.assertEqual(len(assets), 1)
            self.assertEqual(assets[0].name, "Bart")
            self.assertEqual(assets[0].png_b64, "QUFBQQ==")
            self.assertTrue(v2.unlocked)

    def test_rename_replace_delete_without_passphrase(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = self._vault(tmp)
            v.add(SignatureAsset(id="s1", name="old", kind="draw", png_b64="QQ=="))
            v.rename("s1", "new-name")
            self.assertEqual(v.get("s1").name, "new-name")
            v.replace("s1", SignatureAsset(id="ignore", name="replaced", kind="type", text="BK"))
            self.assertEqual(v.get("s1").text, "BK")
            self.assertEqual(v.get("s1").id, "s1")
            v.remove("s1")
            self.assertIsNone(v.get("s1"))

    def test_no_passphrase_api_on_plain_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = self._vault(tmp)
            self.assertFalse(hasattr(v, "set_passphrase") and callable(getattr(v, "unlock", None)) and v.needs_migration)
            v.add(SignatureAsset(id="s1", name="n", kind="image", png_b64="c2VjcmV0cG5n"))
            self.assertNotIn("passphrase", v.path.read_text(encoding="utf-8").lower())


@unittest.skipUnless(HAS_CRYPTO, "cryptography not installed")
class VaultMigrationTests(unittest.TestCase):
    def test_migrate_encrypted_vault_to_plain(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp) / "vault.bin"
            write_legacy_encrypted_vault(
                legacy,
                "correct horse",
                [SignatureAsset(id="s1", name="Bart", kind="draw", png_b64="UNIQUEPIX")],
            )
            self.assertTrue(is_encrypted_vault_bytes(legacy.read_bytes()))
            self.assertNotIn(b"UNIQUEPIX", legacy.read_bytes())
            v = SignatureVault(path=Path(tmp) / "vault.json")
            self.assertTrue(v.needs_migration)
            self.assertFalse(v.unlocked)
            v.migrate("correct horse")
            self.assertFalse(v.needs_migration)
            self.assertTrue(v.unlocked)
            assets = v.list_assets()
            self.assertEqual(len(assets), 1)
            self.assertEqual(assets[0].name, "Bart")
            self.assertEqual(assets[0].png_b64, "UNIQUEPIX")
            plain = v.path.read_text(encoding="utf-8")
            self.assertIn("UNIQUEPIX", plain)
            self.assertTrue(legacy.is_file(), "encrypted original must be left in place")
            self.assertTrue(is_encrypted_vault_bytes(legacy.read_bytes()))

    def test_wrong_passphrase_leaves_encrypted_files_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp) / "vault.bin"
            write_legacy_encrypted_vault(
                legacy,
                "right",
                [SignatureAsset(id="s1", name="secret", kind="image", png_b64="c2VjcmV0cG5n")],
            )
            before = legacy.read_bytes()
            v = SignatureVault(path=Path(tmp) / "vault.json")
            with self.assertRaises(WrongPassphrase) as ctx:
                v.migrate("wrong")
            self.assertIn("Wrong passphrase", str(ctx.exception))
            self.assertTrue(v.needs_migration)
            self.assertFalse(v.unlocked)
            self.assertEqual(legacy.read_bytes(), before)
            self.assertFalse(v.path.exists())

    def test_start_empty_leaves_encrypted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp) / "vault.bin"
            write_legacy_encrypted_vault(
                legacy,
                "pw",
                [SignatureAsset(id="s1", name="keep", kind="draw", png_b64="QQ==")],
            )
            before = legacy.read_bytes()
            v = SignatureVault(path=Path(tmp) / "vault.json")
            v.start_empty_leaving_encrypted()
            self.assertFalse(v.needs_migration)
            self.assertTrue(v.unlocked)
            self.assertEqual(v.list_assets(), [])
            self.assertEqual(legacy.read_bytes(), before)
            self.assertTrue(v.path.is_file())


class EncryptedDetectTests(unittest.TestCase):
    def test_magic_detects_legacy(self):
        self.assertTrue(is_encrypted_vault_bytes(VAULT_MAGIC + b"\x01" + b"x" * 40))
        self.assertFalse(is_encrypted_vault_bytes(b'{"signatures":[]}'))


if __name__ == "__main__":
    unittest.main()
