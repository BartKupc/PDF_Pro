"""Session undo/redo over overlay + page-plan snapshots. Cleared on document close."""

from __future__ import annotations

from typing import Any, Optional

from pdf_pro.overlay import OverlayDocument
from pdf_pro.page_plan import PagePlan


class UndoStack:
    def __init__(
        self,
        document: OverlayDocument,
        plan: Optional[PagePlan] = None,
        limit: int = 100,
    ) -> None:
        self._doc = document
        self._plan = plan
        self._limit = limit
        self._undo: list[Any] = []
        self._redo: list[Any] = []
        self._closed = False

    def bind(self, document: OverlayDocument, plan: Optional[PagePlan] = None) -> None:
        self._doc = document
        if plan is not None:
            self._plan = plan
        self.clear()

    def can_undo(self) -> bool:
        return bool(self._undo) and not self._closed

    def can_redo(self) -> bool:
        return bool(self._redo) and not self._closed

    def _state(self) -> dict[str, Any]:
        state: dict[str, Any] = {
            "overlay": self._doc.snapshot(),
            "page_count": int(self._doc.page_count),
        }
        if self._plan is not None:
            state["plan"] = self._plan.to_dict()
        return state

    def _restore(self, state: Any) -> None:
        if isinstance(state, list):
            self._doc.restore(state)
            return
        self._doc.restore(state["overlay"])
        if "page_count" in state:
            self._doc.page_count = int(state["page_count"])
        if self._plan is not None and state.get("plan") is not None:
            restored = PagePlan.from_dict(state["plan"])
            self._plan.pages[:] = restored.pages

    def checkpoint(self) -> None:
        """Call immediately BEFORE a mutation."""
        if self._closed:
            return
        self._undo.append(self._state())
        if len(self._undo) > self._limit:
            self._undo.pop(0)
        self._redo.clear()

    def discard_if_unchanged(self) -> bool:
        """Drop the last checkpoint when no mutation happened (selection click)."""
        if not self._undo or self._closed:
            return False
        if self._undo[-1] == self._state():
            self._undo.pop()
            return True
        return False

    def undo(self) -> bool:
        if not self.can_undo():
            return False
        self._redo.append(self._state())
        self._restore(self._undo.pop())
        return True

    def redo(self) -> bool:
        if not self.can_redo():
            return False
        self._undo.append(self._state())
        self._restore(self._redo.pop())
        return True

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
        self._closed = False

    def close_document(self) -> None:
        self.clear()
        self._closed = True
