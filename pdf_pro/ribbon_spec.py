"""Ribbon layout — locked grouping for M1 UAT round 2. No Qt."""

from __future__ import annotations

HOME = "Home"
AMEND = "Amend"
SIGN = "Sign"
EXPORT = "Export"

TAB_ORDER = (HOME, AMEND, SIGN, EXPORT)

# action_id -> (tab, group, label)
ACTIONS: dict[str, tuple[str, str, str]] = {
    "open": (HOME, "File", "Open PDF"),
    "prev": (HOME, "Navigate", "Prev"),
    "next": (HOME, "Navigate", "Next"),
    "page_label": (HOME, "Navigate", "Page"),
    "zoom_out": (HOME, "View", "Zoom −"),
    "zoom_in": (HOME, "View", "Zoom +"),
    "fit_width": (HOME, "View", "Fit width"),
    "fit_page": (HOME, "View", "Fit page"),
    "rotate_view": (HOME, "View", "Rotate view"),
    "select": (AMEND, "Tools", "Select"),
    "add_text": (AMEND, "Tools", "Add text"),
    "cover_replace": (AMEND, "Tools", "Cover-and-replace"),
    "whiteout": (AMEND, "Tools", "White-out"),
    "insert_image": (AMEND, "Tools", "Insert image"),
    "undo": (AMEND, "History", "Undo"),
    "redo": (AMEND, "History", "Redo"),
    "font": (AMEND, "Style", "Font"),
    "size": (AMEND, "Style", "Size"),
    "bold": (AMEND, "Style", "Bold"),
    "colour": (AMEND, "Style", "Colour"),
    "draw_signature": (SIGN, "Create", "Draw signature"),
    "type_signature": (SIGN, "Create", "Type signature"),
    "upload_signature": (SIGN, "Create", "Upload signature image"),
    "vault": (SIGN, "Vault", "Vault"),
    "place_initials": (SIGN, "Vault", "Place initials"),
    "preview_export": (EXPORT, "Export", "Preview / Export"),
}

# v0.1.3 toolbar widgets/actions that must still be reachable.
# Legacy "Signature" is split across the Sign tab actions above.
LEGACY_TOOLBAR_ACTIONS = {
    "open",
    "select",
    "add_text",
    "whiteout",
    "cover_replace",
    "insert_image",
    "undo",
    "redo",
    "prev",
    "next",
    "page_label",
    "zoom_in",
    "zoom_out",
    "fit_width",
    "fit_page",
    "rotate_view",
    "preview_export",
    "font",
    "size",
    "bold",
    "colour",
}

SHORTCUTS = {
    "open": "Ctrl+O",
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Shift+Z",
    "zoom_in": "Ctrl+=",
    "zoom_out": "Ctrl+-",
    "preview_export": "Ctrl+E",
    "delete": "Delete",
}

WIDGET_ACTIONS = {"page_label", "font", "size", "bold", "colour"}


def actions_in(tab: str) -> set[str]:
    return {aid for aid, (t, _g, _label) in ACTIONS.items() if t == tab}


def groups_for(tab: str) -> list[str]:
    seen: list[str] = []
    for _aid, (t, group, _label) in ACTIONS.items():
        if t == tab and group not in seen:
            seen.append(group)
    return seen


def action_ids_in_group(tab: str, group: str) -> list[str]:
    return [
        aid
        for aid, (t, g, _label) in ACTIONS.items()
        if t == tab and g == group
    ]
