"""Reject instance-level Qt enum shortcuts (dlg.Accepted crashes bundled PySide6)."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF_PRO = ROOT / "pdf_pro"

# Unscoped enum names that resolve on Qt *classes* via metaclass, but raise
# AttributeError on *instances* with the bundled PySide6.
INSTANCE_ENUM_ATTRS = {
    "Accepted",
    "Rejected",
    "Ok",
    "Cancel",
    "Yes",
    "No",
    "Abort",
    "Retry",
    "Ignore",
    "Apply",
    "Save",
    "Open",
    "Close",
    "AlignCenter",
    "AlignLeft",
    "AlignRight",
    "AlignHCenter",
    "AlignVCenter",
    "AlignTop",
    "AlignBottom",
    "ActionRole",
    "AcceptRole",
    "RejectRole",
    "DestructiveRole",
    "DontUseNativeDialog",
}

# Roots that are Qt namespace/classes (QDialog.Accepted, Qt.AlignCenter, …).
ALLOWED_ROOTS = {
    "Qt",
    "DialogCode",
    "StandardButton",
    "ButtonRole",
    "Option",
    "EchoMode",
    "AlignmentFlag",
    "WidgetAttribute",
    "ItemDataRole",
    "Type",
    "Format",
}


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, ast.Attribute):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    return None


def _is_qt_class_root(name: str) -> bool:
    if name in ALLOWED_ROOTS:
        return True
    # QDialog, QMessageBox, QFileDialog, QImage, QSizePolicy, …
    return len(name) >= 2 and name[0] == "Q" and name[1].isupper()


def _offenders(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr not in INSTANCE_ENUM_ATTRS:
            continue
        root = _root_name(node.value)
        if root is None:
            continue
        if _is_qt_class_root(root):
            continue
        hits.append(f"{path.relative_to(ROOT)}:{node.lineno}: {root}.{node.attr}")
    return hits


class QtInstanceEnumTests(unittest.TestCase):
    def test_no_instance_level_qt_enum_access(self):
        hits: list[str] = []
        for path in PDF_PRO.rglob("*.py"):
            hits.extend(_offenders(path))
        self.assertEqual(
            hits,
            [],
            "use class-scoped Qt enums (QDialog.DialogCode.Accepted), "
            "not instance shortcuts (dlg.Accepted)",
        )


if __name__ == "__main__":
    unittest.main()
