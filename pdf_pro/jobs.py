"""Long-running preview/export/merge work. Qt-free so it can run on a worker thread."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable, Optional

from pdf_pro.export import export_pdf
from pdf_pro.overlay import OverlayDocument
from pdf_pro.page_plan import PagePlan


Progress = Optional[Callable[[int, str], None]]


def render_preview_pages(
    source: Path,
    overlay: OverlayDocument,
    password: Optional[str] = None,
    plan: Optional[PagePlan] = None,
    scale: float = 1.15,
    progress: Progress = None,
) -> list[tuple[int, int, bytes]]:
    """Flatten to a temp PDF and return PNG bytes per page."""
    import fitz

    pages: list[tuple[int, int, bytes]] = []
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "preview.pdf"
        export_pdf(source, overlay, dest, password=password, plan=plan, progress=progress)
        if progress:
            progress(90, "Rendering preview pages")
        doc = fitz.open(dest.as_posix())
        try:
            mat = fitz.Matrix(scale, scale)
            n = doc.page_count
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=mat, alpha=False)
                pages.append((pix.width, pix.height, pix.tobytes("png")))
                if progress:
                    pct = 90 + int(10 * (i + 1) / max(1, n))
                    progress(pct, f"Preview page {i + 1}/{n}")
        finally:
            doc.close()
    return pages
