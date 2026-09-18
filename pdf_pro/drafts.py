"""Local drafts: overlay JSON + source path/sha256 + page plan. Crash recovery."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pdf_pro.overlay import OverlayDocument
from pdf_pro.page_plan import PagePlan
from pdf_pro.paths import app_data_dir


DRAFT_VERSION = 2
MISSING_SOURCE_MESSAGE = (
    "The source PDF is missing. The draft cannot be reopened until the file is restored.\n"
    "PDF_Pro never moves or deletes originals — another process may have relocated it."
)


class DraftError(Exception):
    pass


class MissingSource(DraftError):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"{MISSING_SOURCE_MESSAGE}\nPath: {path}")


def drafts_dir() -> Path:
    path = app_data_dir() / "drafts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_exit_marker() -> Path:
    return app_data_dir() / "clean_exit"


def draft_id_for(source_path: str) -> str:
    return hashlib.sha256(str(source_path).encode("utf-8")).hexdigest()[:16]


def draft_path_for(source_path: str) -> Path:
    return drafts_dir() / f"{draft_id_for(source_path)}.json"


@dataclass
class DraftRecord:
    path: Path
    source_path: str
    source_sha256: str
    saved_at: str
    dirty: bool
    overlay: OverlayDocument
    page_plan: PagePlan

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": DRAFT_VERSION,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "saved_at": self.saved_at,
            "dirty": bool(self.dirty),
            "overlay": self.overlay.to_dict(),
            "page_plan": self.page_plan.to_dict(),
        }


def save_draft(
    overlay: OverlayDocument,
    page_plan: Optional[PagePlan] = None,
    *,
    dirty: bool = True,
    now: Optional[str] = None,
) -> Path:
    source = overlay.source_path or ""
    plan = page_plan or PagePlan.identity(source, overlay.page_count)
    rec = DraftRecord(
        path=draft_path_for(source or "untitled"),
        source_path=source,
        source_sha256=overlay.source_sha256,
        saved_at=now or datetime.now(timezone.utc).isoformat(),
        dirty=dirty,
        overlay=overlay,
        page_plan=plan,
    )
    dest = rec.path
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rec.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(dest)
    return dest


def load_draft(path: Path) -> DraftRecord:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    overlay = OverlayDocument.from_dict(raw.get("overlay") or {})
    plan_raw = raw.get("page_plan")
    if plan_raw:
        plan = PagePlan.from_dict(plan_raw)
    else:
        plan = PagePlan.identity(overlay.source_path, overlay.page_count)
    return DraftRecord(
        path=Path(path),
        source_path=str(raw.get("source_path") or overlay.source_path),
        source_sha256=str(raw.get("source_sha256") or overlay.source_sha256),
        saved_at=str(raw.get("saved_at") or ""),
        dirty=bool(raw.get("dirty")),
        overlay=overlay,
        page_plan=plan,
    )


def list_drafts() -> list[DraftRecord]:
    out = []
    for p in sorted(drafts_dir().glob("*.json")):
        try:
            out.append(load_draft(p))
        except Exception:
            continue
    return out


def mark_clean_exit(now: Optional[str] = None) -> None:
    clean_exit_marker().write_text(now or datetime.now(timezone.utc).isoformat(), encoding="utf-8")


def clear_clean_exit() -> None:
    p = clean_exit_marker()
    if p.is_file():
        p.unlink()


def recover_unsaved() -> list[DraftRecord]:
    """Drafts that look like a crash: dirty and no clean-exit marker, or newer than it."""
    marker = clean_exit_marker()
    marker_text = marker.read_text(encoding="utf-8") if marker.is_file() else ""
    recovered = []
    for rec in list_drafts():
        if not rec.dirty:
            continue
        if not marker_text or rec.saved_at > marker_text:
            recovered.append(rec)
    return recovered


def open_draft(rec: DraftRecord) -> DraftRecord:
    src = Path(rec.source_path)
    if not rec.source_path or not src.is_file():
        raise MissingSource(rec.source_path or "(empty path)")
    return rec


def delete_draft(path: Path) -> None:
    p = Path(path)
    if p.is_file():
        p.unlink()
