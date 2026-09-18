"""Document session: overlay + undo + page plan isolated per open PDF."""

from __future__ import annotations

from pdf_pro.constants import DEFAULT_ZOOM
from pdf_pro.overlay import OverlayDocument
from pdf_pro.page_plan import PagePlan
from pdf_pro.undo import UndoStack


class DocumentSession:
    def __init__(
        self,
        source_path: str = "",
        source_sha256: str = "",
        page_count: int = 0,
        *,
        overlay: OverlayDocument | None = None,
        plan: PagePlan | None = None,
        opened=None,
    ) -> None:
        self.opened = opened
        self.overlay = overlay or OverlayDocument(
            source_path=source_path,
            source_sha256=source_sha256,
            page_count=page_count,
        )
        self.plan = plan or PagePlan.identity(self.overlay.source_path, self.overlay.page_count)
        self.undo = UndoStack(self.overlay)
        self.current_page = 0
        self.zoom = DEFAULT_ZOOM
        self.view_rotation = 0
        self.dirty = False
        self.search_hits: list = []
        self.search_index = -1

    def mark_dirty(self) -> None:
        self.dirty = True

    def close(self) -> None:
        if self.opened is not None:
            try:
                self.opened.close()
            except Exception:
                pass
        self.opened = None
        self.undo.close_document()
