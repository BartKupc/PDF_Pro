"""Silent no-op paths in signature studio must surface a message.

Validation is factored so these tests run without a display / PySide6.
"""

from __future__ import annotations

import unittest

from pdf_pro.overlay import OverlayDocument
from pdf_pro.signature_feedback import (
    MSG_IMAGE_EMPTY,
    MSG_PAD_EMPTY,
    MSG_PASSPHRASE_EMPTY,
    MSG_TYPE_EMPTY,
    MSG_VAULT_LOCKED,
    MSG_VAULT_NO_SELECTION,
    MSG_NAME_EMPTY,
    StudioState,
    place_signature_on_page,
    validate_save_to_vault,
    validate_unlock,
    validate_use_on_page,
)
from pdf_pro.vault import SignatureAsset


def _state(**kwargs) -> StudioState:
    base = dict(
        tab=0,
        pad_has_strokes=False,
        typed_name="",
        image_present=False,
        save_name="Signature",
        vault_unlocked=False,
        vault_selected=False,
        passphrase="",
    )
    base.update(kwargs)
    return StudioState(**base)


class SignatureFeedbackTests(unittest.TestCase):
    def test_use_on_page_empty_pad_is_a_message(self):
        msg = validate_use_on_page(_state(tab=0, pad_has_strokes=False))
        self.assertEqual(msg, MSG_PAD_EMPTY)

    def test_use_on_page_empty_typed_name_is_a_message(self):
        msg = validate_use_on_page(_state(tab=1, typed_name=""))
        self.assertEqual(msg, MSG_TYPE_EMPTY)

    def test_use_on_page_empty_image_is_a_message(self):
        msg = validate_use_on_page(_state(tab=2, image_present=False))
        self.assertEqual(msg, MSG_IMAGE_EMPTY)

    def test_use_on_page_vault_locked_is_a_message(self):
        msg = validate_use_on_page(_state(tab=3, vault_unlocked=False, vault_selected=True))
        self.assertEqual(msg, MSG_VAULT_LOCKED)

    def test_use_on_page_vault_no_selection_is_a_message(self):
        msg = validate_use_on_page(_state(tab=3, vault_unlocked=True, vault_selected=False))
        self.assertEqual(msg, MSG_VAULT_NO_SELECTION)

    def test_save_to_vault_locked_is_a_message(self):
        msg = validate_save_to_vault(_state(tab=0, pad_has_strokes=True, vault_unlocked=False))
        self.assertEqual(msg, MSG_VAULT_LOCKED)

    def test_save_to_vault_empty_name_is_a_message(self):
        msg = validate_save_to_vault(
            _state(tab=0, pad_has_strokes=True, vault_unlocked=True, save_name="  ")
        )
        self.assertEqual(msg, MSG_NAME_EMPTY)

    def test_save_to_vault_empty_pad_is_a_message(self):
        msg = validate_save_to_vault(_state(tab=0, pad_has_strokes=False, vault_unlocked=True))
        self.assertEqual(msg, MSG_PAD_EMPTY)

    def test_unlock_empty_passphrase_is_a_message(self):
        msg = validate_unlock(_state(passphrase=""))
        self.assertEqual(msg, MSG_PASSPHRASE_EMPTY)

    def test_valid_draw_use_has_no_message(self):
        self.assertIsNone(validate_use_on_page(_state(tab=0, pad_has_strokes=True)))

    def test_place_signature_adds_overlay_item(self):
        ov = OverlayDocument()
        asset = SignatureAsset(id="a1", name="Bart", kind="draw", png_b64="QUFB")
        item = place_signature_on_page(ov, asset, page_index=0, page_w=612, page_h=792)
        self.assertEqual(item.type, "signature")
        self.assertEqual(len(list(ov.items_on_page(0))), 1)
        self.assertEqual(ov.items[0].id, item.id)


if __name__ == "__main__":
    unittest.main()
