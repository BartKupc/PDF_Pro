from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from pdf_pro.drafts import (
    MISSING_SOURCE_MESSAGE,
    MissingSource,
    clear_clean_exit,
    load_draft,
    mark_clean_exit,
    open_draft,
    recover_unsaved,
    save_draft,
)
from pdf_pro.overlay import OverlayDocument, make_text
from pdf_pro.page_plan import PagePlan


class DraftTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        os.environ["XDG_DATA_HOME"] = str(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()
        os.environ.pop("XDG_DATA_HOME", None)

    def _overlay(self, src: str = "/tmp/src.pdf") -> OverlayDocument:
        ov = OverlayDocument(source_path=src, source_sha256="deadbeef", page_count=1)
        ov.add(make_text(0, 10, 10, 40, 12, text="hello", italic=True, align="center"))
        return ov

    def test_json_round_trip(self):
        ov = self._overlay()
        plan = PagePlan.identity(ov.source_path, 1)
        path = save_draft(ov, plan, dirty=True, now="2026-01-01T00:00:00+00:00")
        rec = load_draft(path)
        self.assertEqual(rec.source_sha256, "deadbeef")
        self.assertEqual(rec.overlay.items[0].data["text"], "hello")
        self.assertTrue(rec.overlay.items[0].data.get("italic"))
        self.assertEqual(rec.page_plan.pages[0].source_index, 0)
        json.loads(path.read_text(encoding="utf-8"))

    def test_crash_recovery_dirty_without_clean_exit(self):
        ov = self._overlay("/tmp/crash.pdf")
        save_draft(ov, dirty=True, now="2026-02-01T00:00:00+00:00")
        clear_clean_exit()
        found = recover_unsaved()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].source_path, "/tmp/crash.pdf")

    def test_clean_exit_hides_older_draft(self):
        ov = self._overlay("/tmp/ok.pdf")
        save_draft(ov, dirty=True, now="2026-01-01T00:00:00+00:00")
        mark_clean_exit("2026-01-02T00:00:00+00:00")
        self.assertEqual(recover_unsaved(), [])

    def test_missing_source_message(self):
        ov = self._overlay(str(self.root / "gone.pdf"))
        path = save_draft(ov, dirty=True)
        rec = load_draft(path)
        with self.assertRaises(MissingSource) as ctx:
            open_draft(rec)
        self.assertIn("missing", str(ctx.exception).lower())
        self.assertIn(MISSING_SOURCE_MESSAGE.split(".")[0], str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
