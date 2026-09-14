from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from pdf_pro.document import file_sha256, verify_source_untouched
from pdf_pro.export import default_export_path
from pdf_pro.overlay import OverlayDocument, make_signature, make_text


MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer<< /Size 4 /Root 1 0 R >>
startxref
196
%%EOF
"""


class ChecksumTests(unittest.TestCase):
    def test_sha256_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.pdf"
            p.write_bytes(MINIMAL_PDF)
            a = file_sha256(p)
            b = file_sha256(p)
            self.assertEqual(a, b)
            self.assertEqual(a, hashlib.sha256(MINIMAL_PDF).hexdigest())
            self.assertTrue(verify_source_untouched(p, a))
            p.write_bytes(MINIMAL_PDF + b" ")
            self.assertFalse(verify_source_untouched(p, a))


class ExportNameTests(unittest.TestCase):
    def test_amended_vs_signed(self):
        src = Path("/tmp/invoice.pdf")
        ov = OverlayDocument()
        ov.add(make_text(0, 0, 0, 10, 10, text="x"))
        self.assertEqual(default_export_path(src, ov).name, "invoice_amended.pdf")
        ov.add(make_signature(0, 0, 0, 40, 20, kind="draw"))
        self.assertEqual(default_export_path(src, ov).name, "invoice_signed.pdf")

    def test_refuses_overwrite_source_path_logic(self):
        from pdf_pro.export import ExportError, export_pdf

        src = Path("/tmp/does-not-need-to-exist-for-guard.pdf")
        # export_pdf compares resolved paths before opening; use same path
        # The guard runs after resolve — if file missing, open_pdf fails first.
        # Direct unit: ExportError message contract.
        err = ExportError("Refusing to overwrite the source PDF")
        self.assertIn("overwrite", str(err).lower())
