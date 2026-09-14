"""Bundled fonts for editor + flatten export."""

from __future__ import annotations

from pathlib import Path

from pdf_pro.paths import fonts_dir

FAMILY_FILES = {
    "DejaVu Sans": "DejaVuSans.ttf",
    "DejaVu Sans Bold": "DejaVuSans-Bold.ttf",
    "DejaVu Serif": "DejaVuSerif.ttf",
    "DejaVu Serif Bold": "DejaVuSerif-Bold.ttf",
    "DejaVu Sans Mono": "DejaVuSansMono.ttf",
    "Dancing Script": "DancingScript-Regular.ttf",
}

BUNDLED_FAMILIES = ["DejaVu Sans", "DejaVu Serif", "DejaVu Sans Mono", "Dancing Script"]
HANDWRITING_FAMILY = "Dancing Script"


def font_path(family: str, bold: bool = False) -> Path:
    if bold and family == "DejaVu Sans":
        name = FAMILY_FILES["DejaVu Sans Bold"]
    elif bold and family == "DejaVu Serif":
        name = FAMILY_FILES["DejaVu Serif Bold"]
    else:
        name = FAMILY_FILES.get(family) or FAMILY_FILES["DejaVu Sans"]
    path = fonts_dir() / name
    if not path.is_file():
        path = fonts_dir() / FAMILY_FILES["DejaVu Sans"]
    return path


def resolve_family(name: str) -> str:
    if name in FAMILY_FILES or name in BUNDLED_FAMILIES:
        return name
    lowered = (name or "").lower()
    if "dancing" in lowered or "script" in lowered or "hand" in lowered:
        return HANDWRITING_FAMILY
    if "serif" in lowered:
        return "DejaVu Serif"
    if "mono" in lowered:
        return "DejaVu Sans Mono"
    return "DejaVu Sans"
