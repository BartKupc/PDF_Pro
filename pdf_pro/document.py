"""Open PDFs read-only. Never bypass encryption. Detect existing digital signatures."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import threading

from pdf_pro.constants import CORRUPT_NOTICE, PASSWORD_WRONG, UNSUPPORTED_NOTICE


class PdfError(Exception):
    pass


class NeedsPassword(PdfError):
    pass


class WrongPassword(PdfError):
    def __init__(self) -> None:
        super().__init__(PASSWORD_WRONG)


class CorruptPdf(PdfError):
    def __init__(self, message: str = CORRUPT_NOTICE) -> None:
        super().__init__(message)


class UnsupportedPdf(PdfError):
    def __init__(self, message: str = UNSUPPORTED_NOTICE) -> None:
        super().__init__(message)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _fitz():
    try:
        import fitz
    except ImportError as exc:
        raise PdfError("PyMuPDF (fitz) is required") from exc
    return fitz


def detect_digital_signature(doc) -> bool:
    """True if the PDF has a signature dictionary / signature widget / is_signed."""
    try:
        if bool(getattr(doc, "is_signed", False)):
            return True
    except Exception:
        pass
    fitz = None
    try:
        import fitz as _fz
        fitz = _fz
    except ImportError:
        fitz = None
    sig_type = getattr(fitz, "PDF_WIDGET_TYPE_SIGNATURE", None) if fitz else None
    try:
        for page in doc:
            widgets = page.widgets()
            if not widgets:
                continue
            for w in widgets:
                if sig_type is not None and getattr(w, "field_type", None) == sig_type:
                    return True
                ft = str(getattr(w, "field_type_string", "") or "").lower()
                if "sig" in ft:
                    return True
    except Exception:
        pass
    try:
        # Catalog /AcroForm /SigFlags or xref scan
        for xref in range(1, doc.xref_length()):
            try:
                raw = doc.xref_object(xref) or ""
            except Exception:
                continue
            if "/Type /Sig" in raw or "/FT /Sig" in raw:
                return True
    except Exception:
        pass
    return False


@dataclass
class OpenedPdf:
    path: Path
    password: Optional[str]
    sha256: str
    page_count: int
    encrypted: bool
    has_digital_signature: bool
    _doc: object
    _lock: threading.RLock = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._lock is None:
            object.__setattr__(self, "_lock", threading.RLock())

    def close(self) -> None:
        with self._lock:
            try:
                self._doc.close()
            except Exception:
                pass

    def page_size(self, index: int) -> tuple[float, float]:
        with self._lock:
            page = self._doc[index]
            rect = page.rect
            return float(rect.width), float(rect.height)

    def render_pixmap(self, index: int, scale: float = 1.5):
        fitz = _fitz()
        with self._lock:
            page = self._doc[index]
            mat = fitz.Matrix(scale, scale)
            return page.get_pixmap(matrix=mat, alpha=False)

    @property
    def fitz_doc(self):
        return self._doc


def open_pdf(path: str | Path, password: Optional[str] = None) -> OpenedPdf:
    path = Path(path)
    if not path.is_file():
        raise UnsupportedPdf(f"File not found: {path}")
    if path.suffix.lower() != ".pdf":
        # still try — some PDFs have no suffix — but give a clear error if fitz fails
        pass
    sha = file_sha256(path)
    fitz = _fitz()
    try:
        doc = fitz.open(path.as_posix())
    except Exception as exc:
        raise CorruptPdf() from exc

    encrypted = bool(doc.is_encrypted)
    if encrypted:
        if not password:
            doc.close()
            raise NeedsPassword()
        rc = doc.authenticate(password)
        if not rc:
            doc.close()
            raise WrongPassword()

    if doc.page_count < 1:
        doc.close()
        raise CorruptPdf("This PDF has no pages.")

    try:
        signed = detect_digital_signature(doc)
    except Exception:
        signed = False

    return OpenedPdf(
        path=path.resolve(),
        password=password,
        sha256=sha,
        page_count=doc.page_count,
        encrypted=encrypted,
        has_digital_signature=signed,
        _doc=doc,
    )


def verify_source_untouched(path: Path, expected_sha256: str) -> bool:
    return file_sha256(path) == expected_sha256
