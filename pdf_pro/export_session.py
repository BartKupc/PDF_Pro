"""Post-preview export orchestration. No Qt — testable offscreen."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from pdf_pro.export import ExportError


@dataclass
class ExportResult:
    cancelled: bool
    path: Optional[Path]
    message: str


def complete_export(
    source: Path,
    overlay,
    dest: Optional[Path],
    *,
    password: Optional[str] = None,
    source_sha: Optional[str] = None,
    export_fn: Optional[Callable] = None,
    assert_fn: Optional[Callable] = None,
    verify_fn: Optional[Callable] = None,
) -> ExportResult:
    """Finish export after preview was accepted.

    ``dest is None`` means the user cancelled the save dialog (not an error).
    Any other failure raises ExportError (or the underlying OSError).
    """
    if dest is None:
        return ExportResult(cancelled=True, path=None, message="")
    if assert_fn is None:
        from pdf_pro.export import assert_export_destination

        assert_fn = assert_export_destination
    dest = assert_fn(source, dest)
    if export_fn is None:
        from pdf_pro.export import export_pdf

        export_fn = export_pdf
    export_fn(source, overlay, dest, password=password)
    if source_sha is not None:
        if verify_fn is None:
            from pdf_pro.document import verify_source_untouched

            verify_fn = verify_source_untouched
        if not verify_fn(source, source_sha):
            raise ExportError("Source checksum changed — export may be unsafe.")
    return ExportResult(
        cancelled=False,
        path=dest,
        message=f"Exported to {dest}\nSource file is unchanged.",
    )


def open_containing_folder(
    path: Path,
    opener: Optional[Callable[[str], object]] = None,
) -> None:
    directory = str(Path(path).parent)
    if opener is not None:
        opener(directory)
        return
    subprocess.Popen(["xdg-open", directory], start_new_session=True)
