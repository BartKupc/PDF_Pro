"""Tag render jobs as page vs thumbnail. Never infer kind from zoom scale."""

from __future__ import annotations

from typing import Optional

KIND_PAGE = "page"
KIND_THUMB = "thumb"


def destination(kind: Optional[str], scale: float | None = None) -> str:
    """Return 'page' or 'thumbnail'. Kind wins; scale is ignored on purpose."""
    if kind == KIND_THUMB:
        return "thumbnail"
    return "page"
