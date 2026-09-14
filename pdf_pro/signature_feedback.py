"""Signature-studio validation messages. No Qt — testable offscreen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pdf_pro.fonts import HANDWRITING_FAMILY
from pdf_pro.overlay import OverlayDocument, make_signature
from pdf_pro.vault import SignatureAsset

MSG_PAD_EMPTY = "Draw a signature on the pad first."
MSG_TYPE_EMPTY = "Type a name for the signature first."
MSG_IMAGE_EMPTY = "Upload a PNG or JPEG image first."
MSG_NAME_EMPTY = "Enter a name in the Save as field."
MSG_VAULT_LOCKED = "Unlock the vault first."
MSG_PASSPHRASE_EMPTY = "Enter a passphrase."
MSG_VAULT_NO_SELECTION = "Select a saved signature from the vault."
MSG_SAVED = "Saved to the vault."


@dataclass(frozen=True)
class StudioState:
    tab: int
    pad_has_strokes: bool
    typed_name: str
    image_present: bool
    save_name: str
    vault_unlocked: bool
    vault_selected: bool
    passphrase: str = ""


def _content_error(state: StudioState) -> Optional[str]:
    if state.tab == 0:
        if not state.pad_has_strokes:
            return MSG_PAD_EMPTY
    elif state.tab == 1:
        if not (state.typed_name or "").strip():
            return MSG_TYPE_EMPTY
    elif state.tab == 2:
        if not state.image_present:
            return MSG_IMAGE_EMPTY
    elif state.tab == 3:
        if not state.vault_unlocked:
            return MSG_VAULT_LOCKED
        if not state.vault_selected:
            return MSG_VAULT_NO_SELECTION
    return None


def validate_use_on_page(state: StudioState) -> Optional[str]:
    return _content_error(state)


def validate_save_to_vault(state: StudioState) -> Optional[str]:
    if not state.vault_unlocked:
        return MSG_VAULT_LOCKED
    if not (state.save_name or "").strip():
        return MSG_NAME_EMPTY
    return _content_error(state)


def validate_unlock(state: StudioState) -> Optional[str]:
    if not (state.passphrase or "").strip():
        return MSG_PASSPHRASE_EMPTY
    return None


def place_signature_on_page(
    overlay: OverlayDocument,
    asset: SignatureAsset,
    page_index: int,
    page_w: float,
    page_h: float,
):
    """Add a signature overlay on the current page (visible after canvas bind)."""
    width = min(180.0, float(page_w) * 0.35)
    height = width * 0.35
    y = max(8.0, float(page_h) - 100.0)
    item = make_signature(
        page_index,
        72.0,
        y,
        width,
        height,
        kind=asset.kind,
        png_b64=asset.png_b64,
        strokes=asset.strokes,
        text=asset.text,
        font_family=asset.font_family or HANDWRITING_FAMILY,
        vault_id=asset.id or "",
    )
    overlay.add(item)
    return item
