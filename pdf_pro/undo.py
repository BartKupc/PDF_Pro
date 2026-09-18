"""Session undo/redo over overlay snapshots. Cleared on document close."""

from __future__ import annotations

from typing import Callable, Optional

from pdf_pro.overlay import OverlayDocument


class UndoStack:
    def __init__(self, document: OverlayDocument, limit: int = 100) -> None:
        self._doc = document
        self._limit = limit
        self._undo: list[list] = []
        self._redo: list[list] = []
        self._closed = False

    def bind(self, document: OverlayDocument) -> None:
        self._doc = document
        self.clear()

    def can_undo(self) -> bool:
        return bool(self._undo) and not self._closed

    def can_redo(self) -> bool:
        return bool(self._redo) and not self._closed

    def checkpoint(self) -> None:
        """Call immediately BEFORE a mutation."""
        if self._closed:
            return
        self._undo.append(self._doc.snapshot())
        if len(self._undo) > self._limit:
            self._undo.pop(0)
        self._redo.clear()

    def discard_if_unchanged(self) -> bool:
        """Drop the last checkpoint when no mutation happened (selection click)."""
        if not self._undo or self._closed:
            return False
        if self._undo[-1] == self._doc.snapshot():
            self._undo.pop()
            return True
        return False

    def undo(self) -> bool:
        if not self.can_undo():
            return False
        self._redo.append(self._doc.snapshot())
        self._doc.restore(self._undo.pop())
        return True

    def redo(self) -> bool:
        if not self.can_redo():
            return False
        self._undo.append(self._doc.snapshot())
        self._doc.restore(self._redo.pop())
        return True

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
        self._closed = False

    def close_document(self) -> None:
        self.clear()
        self._closed = True
