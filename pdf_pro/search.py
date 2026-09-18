"""Search hits on a text-layer PDF. Qt-free."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class SearchHit:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    def rect(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


def search_page_words(words: Iterable[tuple], query: str, page: int) -> list[SearchHit]:
    """words: iterable of (x0, y0, x1, y1, text, ...) as from page.get_text('words')."""
    needle = (query or "").strip().lower()
    if not needle:
        return []
    hits: list[SearchHit] = []
    tokens = needle.split()
    word_list = list(words)
    for i, w in enumerate(word_list):
        text = str(w[4]) if len(w) > 4 else ""
        if needle in text.lower():
            hits.append(
                SearchHit(
                    page=page,
                    x0=float(w[0]),
                    y0=float(w[1]),
                    x1=float(w[2]),
                    y1=float(w[3]),
                    text=text,
                )
            )
            continue
        if len(tokens) > 1:
            window = word_list[i : i + len(tokens)]
            joined = " ".join(str(x[4]) for x in window if len(x) > 4)
            if joined.lower() == needle or needle in joined.lower():
                hits.append(
                    SearchHit(
                        page=page,
                        x0=float(window[0][0]),
                        y0=min(float(x[1]) for x in window),
                        x1=float(window[-1][2]),
                        y1=max(float(x[3]) for x in window),
                        text=joined,
                    )
                )
    return hits


def copy_text_from_hits(hits: Iterable[SearchHit]) -> str:
    return " ".join(h.text for h in hits)


def search_fitz_doc(doc: Any, query: str) -> list[SearchHit]:
    """PyMuPDF document search. Uses search_for when available."""
    needle = (query or "").strip()
    if not needle:
        return []
    hits: list[SearchHit] = []
    for i, page in enumerate(doc):
        try:
            rects = page.search_for(needle)
        except Exception:
            rects = []
        if rects:
            for r in rects:
                hits.append(
                    SearchHit(
                        page=i,
                        x0=float(r.x0),
                        y0=float(r.y0),
                        x1=float(r.x1),
                        y1=float(r.y1),
                        text=needle,
                    )
                )
            continue
        try:
            words = page.get_text("words") or []
        except Exception:
            words = []
        hits.extend(search_page_words(words, needle, i))
    return hits
