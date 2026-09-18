"""Qt file dialogs — always non-native.

Native GTK/portal dialogs die silently on some Ubuntu machines behind
atk-bridge ``GetDeviceEvents`` / undefined-symbol warnings.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog

NON_NATIVE = QFileDialog.DontUseNativeDialog


def get_open_file_name(parent, caption: str, directory: str = "", filter: str = ""):
    return QFileDialog.getOpenFileName(
        parent, caption, directory, filter, options=NON_NATIVE
    )


def get_save_file_name(parent, caption: str, directory: str = "", filter: str = ""):
    return QFileDialog.getSaveFileName(
        parent, caption, directory, filter, options=NON_NATIVE
    )
