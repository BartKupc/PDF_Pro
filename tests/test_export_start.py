"""Export-start failures must raise ExportError (reason + path), never silent."""

from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from pdf_pro.export import ExportError, assert_export_destination


class ExportStartTests(unittest.TestCase):
    def test_refuses_source_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "doc.pdf"
            src.write_bytes(b"%PDF-1.4\n")
            with self.assertRaises(ExportError) as ctx:
                assert_export_destination(src, src)
            text = str(ctx.exception)
            self.assertIn("overwrite", text.lower())
            self.assertIn(str(src), text)

    def test_missing_parent_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "doc.pdf"
            src.write_bytes(b"%PDF-1.4\n")
            dest = Path(tmp) / "nope" / "out.pdf"
            with self.assertRaises(ExportError) as ctx:
                assert_export_destination(src, dest)
            text = str(ctx.exception)
            self.assertIn("does not exist", text.lower())
            self.assertIn(str(dest.parent), text)

    def test_unwritable_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "doc.pdf"
            src.write_bytes(b"%PDF-1.4\n")
            locked = Path(tmp) / "locked"
            locked.mkdir()
            dest = locked / "out.pdf"
            os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
            try:
                if os.access(locked, os.W_OK):
                    self.skipTest("running as root; chmod does not drop write")
                with self.assertRaises(ExportError) as ctx:
                    assert_export_destination(src, dest)
                text = str(ctx.exception)
                self.assertIn("not writable", text.lower())
                self.assertIn(str(locked), text)
            finally:
                os.chmod(locked, stat.S_IRWXU)

    def test_ok_destination_returns_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "doc.pdf"
            src.write_bytes(b"%PDF-1.4\n")
            dest = Path(tmp) / "out.pdf"
            got = assert_export_destination(src, dest)
            self.assertEqual(got, dest)


if __name__ == "__main__":
    unittest.main()
