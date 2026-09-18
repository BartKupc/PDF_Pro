"""kill -9 mid-edit simulation: dirty draft restored, missing source messaged."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pdf_pro.drafts import (
    MissingSource,
    clear_clean_exit,
    load_draft,
    open_draft,
    recover_unsaved,
    save_draft,
)
from pdf_pro.overlay import OverlayDocument, make_text


class CrashRecoveryDrill(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        os.environ["XDG_DATA_HOME"] = str(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()
        os.environ.pop("XDG_DATA_HOME", None)

    def test_kill_dash_nine_mid_edit_restores_draft(self):
        src = self.root / "live.pdf"
        src.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
        ov = OverlayDocument(source_path=str(src), source_sha256="abc", page_count=1)
        ov.add(make_text(0, 12, 12, 80, 16, text="unsaved-edit"))
        save_draft(ov, dirty=True, now="2026-04-01T00:00:00+00:00")
        clear_clean_exit()  # process died before clean exit
        found = recover_unsaved()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].overlay.items[0].data["text"], "unsaved-edit")
        rec = open_draft(found[0])
        self.assertEqual(rec.source_path, str(src))

    def test_missing_source_after_recovery(self):
        ov = OverlayDocument(source_path=str(self.root / "gone.pdf"), source_sha256="x", page_count=1)
        path = save_draft(ov, dirty=True)
        rec = load_draft(path)
        with self.assertRaises(MissingSource) as ctx:
            open_draft(rec)
        self.assertIn("missing", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
