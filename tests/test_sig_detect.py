from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pdf_pro.document import detect_digital_signature


SIG_PDF = b"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R /AcroForm 5 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Annots [4 0 R] >>endobj
4 0 obj<< /Type /Annot /Subtype /Widget /FT /Sig /T (Sig1) /Rect [0 0 100 50] /P 3 0 R /V 6 0 R >>endobj
5 0 obj<< /Fields [4 0 R] /SigFlags 3 >>endobj
6 0 obj<< /Type /Sig /Filter /Adobe.PPKLite /SubFilter /adbe.pkcs7.detached /ByteRange [0 0 0 0] /Contents <00> >>endobj
xref
0 7
0000000000 65535 f 
0000000009 00000 n 
0000000078 00000 n 
0000000135 00000 n 
0000000224 00000 n 
0000000348 00000 n 
0000000399 00000 n 
trailer<< /Size 7 /Root 1 0 R >>
startxref
520
%%EOF
"""


class SignatureDetectUnit(unittest.TestCase):
    def test_sig_dict_in_bytes_fallback(self):
        # Without PyMuPDF we still document the detector contract via a fake doc.
        class Fake:
            is_signed = False

            def __iter__(self):
                return iter(())

            def xref_length(self):
                return 7

            def xref_object(self, xref):
                if xref == 6:
                    return "<< /Type /Sig /Filter /Adobe.PPKLite >>"
                return "<< >>"

        self.assertTrue(detect_digital_signature(Fake()))

    def test_unsigned_fake(self):
        class Fake:
            is_signed = False

            def __iter__(self):
                return iter(())

            def xref_length(self):
                return 2

            def xref_object(self, xref):
                return "<< /Type /Page >>"

        self.assertFalse(detect_digital_signature(Fake()))

    def test_detect_on_widget_fixture_pdf(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF not installed")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sig-widget.pdf"
            path.write_bytes(SIG_PDF)
            doc = fitz.open(path.as_posix())
            try:
                self.assertTrue(detect_digital_signature(doc))
            finally:
                doc.close()
