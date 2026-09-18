"""Ribbon layout. Dark theme only; keep 1366px-wide groups compact."""

from __future__ import annotations

HOME = "Home"
AMEND = "Amend"
PAGES = "Pages"
SIGN = "Sign"
EXPORT = "Export"

TAB_ORDER = (HOME, AMEND, PAGES, SIGN, EXPORT)

# action_id -> (tab, group, label)
ACTIONS: dict[str, tuple[str, str, str]] = {
    "open": (HOME, "File", "Open"),
    "drafts": (HOME, "File", "Drafts"),
    "history": (HOME, "File", "History"),
    "wipe": (HOME, "File", "Wipe local data"),
    "search_box": (HOME, "Find", "Find"),
    "find_prev": (HOME, "Find", "Prev hit"),
    "find_next": (HOME, "Find", "Next hit"),
    "copy_hit": (HOME, "Find", "Copy"),
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
    "shape_rect": (AMEND, "Shapes", "Rect"),
    "shape_line": (AMEND, "Shapes", "Line"),
    "shape_arrow": (AMEND, "Shapes", "Arrow"),
    "shape_ellipse": (AMEND, "Shapes", "Circle"),
    "shape_highlight": (AMEND, "Shapes", "Highlight"),
    "shape_underline": (AMEND, "Shapes", "Underline"),
    "shape_strike": (AMEND, "Shapes", "Strike"),
    "shape_pen": (AMEND, "Shapes", "Pen"),
    "undo": (AMEND, "History", "Undo"),
    "redo": (AMEND, "History", "Redo"),
    "font": (AMEND, "Style", "Font"),
    "size": (AMEND, "Style", "Size"),
    "bold": (AMEND, "Style", "Bold"),
    "italic": (AMEND, "Style", "Italic"),
    "underline": (AMEND, "Style", "U"),
    "align": (AMEND, "Style", "Align"),
    "colour": (AMEND, "Style", "Colour"),
    "rotate_item": (AMEND, "Arrange", "Rotate"),
    "duplicate_item": (AMEND, "Arrange", "Duplicate"),
    "bring_front": (AMEND, "Arrange", "Front"),
    "send_back": (AMEND, "Arrange", "Back"),
    "page_rotate": (PAGES, "Page", "Rotate 90°"),
    "page_delete": (PAGES, "Page", "Delete"),
    "page_duplicate": (PAGES, "Page", "Duplicate"),
    "page_up": (PAGES, "Order", "Move up"),
    "page_down": (PAGES, "Order", "Move down"),
    "page_extract": (PAGES, "File", "Extract"),
    "page_merge": (PAGES, "File", "Merge PDF"),
    "draw_signature": (SIGN, "Create", "Draw signature"),
    "type_signature": (SIGN, "Create", "Type signature"),
    "upload_signature": (SIGN, "Create", "Upload signature image"),
    "vault": (SIGN, "Vault", "Vault"),
    "place_initials": (SIGN, "Vault", "Place initials"),
    "sig_date": (SIGN, "Label", "Date"),
    "sig_label": (SIGN, "Label", "Name"),
    "preview_export": (EXPORT, "Export", "Preview / Export"),
}

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
    "find": "Ctrl+F",
}

WIDGET_ACTIONS = {
    "page_label",
    "font",
    "size",
    "bold",
    "colour",
    "search_box",
    "italic",
    "underline",
    "align",
    "sig_date",
    "sig_label",
}


def actions_in(tab: str) -> set[str]:
    return {aid for aid, (t, _g, _label) in ACTIONS.items() if t == tab}


def groups_for(tab: str) -> list[str]:
    seen: list[str] = []
    for _aid, (t, group, _label) in ACTIONS.items():
        if t == tab and group not in seen:
            seen.append(group)
    return seen


def action_ids_in_group(tab: str, group: str) -> list[str]:
    return [aid for aid, (t, g, _label) in ACTIONS.items() if t == tab and g == group]
