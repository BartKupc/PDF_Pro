"""Assemble a working fitz document from a PagePlan. Never writes the source."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pdf_pro.page_plan import PagePlan


class ComposeError(Exception):
    pass


def compose_work_doc(plan: PagePlan, passwords: Optional[dict[str, str]] = None):
    try:
        import fitz
    except ImportError as exc:
        raise ComposeError("PyMuPDF (fitz) is required") from exc
    if not plan.pages:
        raise ComposeError("Page plan is empty")
    passwords = passwords or {}
    out = fitz.open()
    cache: dict[str, object] = {}
    try:
        for ref in plan.pages:
            src = cache.get(ref.source_path)
            if src is None:
                path = Path(ref.source_path)
                if not path.is_file():
                    raise ComposeError(f"Source PDF missing: {path}")
                src = fitz.open(path.as_posix())
                if src.is_encrypted:
                    pw = passwords.get(ref.source_path) or passwords.get(str(path))
                    if not pw or not src.authenticate(pw):
                        src.close()
                        raise ComposeError(f"Could not decrypt {path.name} for page ops")
                cache[ref.source_path] = src
            if ref.source_index < 0 or ref.source_index >= src.page_count:
                raise ComposeError(f"Page {ref.source_index + 1} missing in {ref.source_path}")
            out.insert_pdf(src, from_page=ref.source_index, to_page=ref.source_index)
            if ref.rotation:
                page = out[-1]
                page.set_rotation((int(page.rotation) + int(ref.rotation)) % 360)
        return out
    except Exception:
        try:
            out.close()
        except Exception:
            pass
        raise
    finally:
        for doc in cache.values():
            try:
                doc.close()
            except Exception:
                pass


def write_plan_pdf(plan: PagePlan, dest: Path, passwords: Optional[dict[str, str]] = None) -> Path:
    """Write composed pages (no overlays) — extract/merge output."""
    import os

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    work = compose_work_doc(plan, passwords=passwords)
    tmp = dest.with_name(dest.name + ".partial")
    try:
        if tmp.exists():
            tmp.unlink()
        work.save(tmp.as_posix(), garbage=4, deflate=True)
        os.replace(tmp.as_posix(), dest.as_posix())
        return dest
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise
    finally:
        work.close()
