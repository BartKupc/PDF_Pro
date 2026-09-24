from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pdf_pro.history import WIPE_NOTICE, delete_entry, load_history, record_export, wipe_local_data
from pdf_pro.overlay import OverlayDocument, make_text
from pdf_pro.drafts import save_draft
from pdf_pro.vault import SignatureAsset, SignatureVault


class HistoryWipeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        os.environ["XDG_DATA_HOME"] = str(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()
        os.environ.pop("XDG_DATA_HOME", None)

    def test_history_lists_fields(self):
        entry = record_export(
            "/docs/letter.pdf",
            "/docs/letter_signed.pdf",
            kind="signed",
            project="letter",
            when="2026-03-01T12:00:00+00:00",
        )
        self.assertEqual(entry["original"], "/docs/letter.pdf")
        self.assertEqual(entry["project"], "letter")
        self.assertEqual(entry["datetime"], "2026-03-01T12:00:00+00:00")
        self.assertEqual(entry["kind"], "signed")
        self.assertEqual(entry["export_path"], "/docs/letter_signed.pdf")
        listed = load_history()
        self.assertEqual(len(listed), 1)
        delete_entry(0)
        self.assertEqual(load_history(), [])

    def test_wipe_removes_drafts_vault_history_temp(self):
        ov = OverlayDocument(source_path="/tmp/a.pdf", source_sha256="aa", page_count=1)
        ov.add(make_text(0, 0, 0, 10, 10, text="x"))
        save_draft(ov, dirty=True)
        record_export("/tmp/a.pdf", "/tmp/a_amended.pdf", kind="amended")
        vault = SignatureVault(path=self.root / "pdf_pro" / "vault" / "vault.json")
        vault.add(SignatureAsset(id="s1", name="n", kind="draw", png_b64="QQ=="))
        tmp = self.root / "pdf_pro" / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / "partial.pdf").write_bytes(b"%PDF")
        result = wipe_local_data(vault_path=vault.path)
        self.assertTrue(result["ok"], result)
        self.assertIn("drafts", " ".join(result["removed"]))
        self.assertFalse(vault.path.is_file())
        self.assertEqual(load_history(), [])
        self.assertFalse((tmp / "partial.pdf").exists())
        self.assertIn("permanently deletes", WIPE_NOTICE.lower())
        self.assertIn("not deleted", WIPE_NOTICE.lower())


if __name__ == "__main__":
    unittest.main()
