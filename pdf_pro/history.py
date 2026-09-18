"""Local export history + privacy wipe. No network."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pdf_pro.paths import app_data_dir, vault_file


WIPE_NOTICE = (
    "This permanently deletes drafts, the signature vault, export history, "
    "and temporary files stored by PDF_Pro on this machine. "
    "Original PDFs you opened are not deleted. This cannot be undone."
)


def history_path() -> Path:
    return app_data_dir() / "history.json"


def temp_dir() -> Path:
    path = app_data_dir() / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_history() -> list[dict[str, Any]]:
    p = history_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    return list(data.get("entries") or [])


def save_history(entries: list[dict[str, Any]]) -> None:
    dest = history_path()
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"version": 1, "entries": entries}, indent=2), encoding="utf-8")
    tmp.replace(dest)


def record_export(
    original: str | Path,
    dest: str | Path,
    *,
    kind: str = "amended",
    project: str = "",
    when: Optional[str] = None,
) -> dict[str, Any]:
    original = Path(original)
    dest = Path(dest)
    entry = {
        "original": str(original),
        "project": project or original.stem,
        "datetime": when or datetime.now(timezone.utc).isoformat(),
        "kind": "signed" if kind == "signed" else "amended",
        "export_path": str(dest),
    }
    entries = load_history()
    entries.append(entry)
    save_history(entries)
    return entry


def delete_entry(index: int) -> None:
    entries = load_history()
    if 0 <= index < len(entries):
        entries.pop(index)
        save_history(entries)


def _rm(path: Path, removed: list[str]) -> None:
    if path.is_file():
        path.unlink()
        removed.append(str(path))
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
        removed.append(str(path))


def wipe_local_data(*, vault_path: Optional[Path] = None) -> dict[str, Any]:
    """Delete drafts, vault, history, temp. Original PDFs are not touched."""
    from pdf_pro.drafts import clean_exit_marker
    from pdf_pro.paths import app_data_dir

    removed: list[str] = []
    drafts = app_data_dir() / "drafts"
    _rm(drafts, removed)
    _rm(history_path(), removed)
    _rm(clean_exit_marker(), removed)
    vpath = Path(vault_path) if vault_path else vault_file()
    _rm(vpath, removed)
    vault_parent = vpath.parent
    if vault_parent.is_dir() and vault_parent.name == "vault":
        _rm(vault_parent, removed)
    tmp = app_data_dir() / "tmp"
    _rm(tmp, removed)

    def _still(path: Path) -> bool:
        if path.is_file():
            return True
        if path.is_dir():
            try:
                return any(path.iterdir())
            except OSError:
                return False
        return False

    leftover = [str(p) for p in (drafts, history_path(), vpath, tmp) if _still(p)]
    return {"removed": removed, "leftover": leftover, "ok": not leftover, "notice": WIPE_NOTICE}
