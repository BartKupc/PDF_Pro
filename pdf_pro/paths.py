"""Local paths. No network. Vault lives under XDG data home."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _meipass() -> Path | None:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return None


def app_data_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        root = Path(xdg)
    else:
        root = Path.home() / ".local" / "share"
    path = root / "pdf_pro"
    path.mkdir(parents=True, exist_ok=True)
    return path


def vault_dir() -> Path:
    path = app_data_dir() / "vault"
    path.mkdir(parents=True, exist_ok=True)
    return path


def vault_file() -> Path:
    return vault_dir() / "vault.bin"


def package_dir() -> Path:
    mp = _meipass()
    if mp is not None:
        return mp / "pdf_pro"
    return Path(__file__).resolve().parent


def fonts_dir() -> Path:
    return package_dir() / "fonts"


def assets_dir() -> Path:
    mp = _meipass()
    here = package_dir()
    candidates = []
    if mp is not None:
        candidates.append(mp / "assets")
    candidates.extend(
        [
            here.parent / "assets",
            here / "assets",
            Path(os.environ.get("PDF_PRO_ASSETS", "")),
        ]
    )
    for c in candidates:
        if c and ((c / "pdf_pro_icon.svg").exists() or (c / "pdf_pro_icon_256.png").exists()):
            return c
    return here.parent / "assets"


def icon_path(size: int = 256) -> Path:
    return assets_dir() / f"pdf_pro_icon_{size}.png"
