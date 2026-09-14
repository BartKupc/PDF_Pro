"""Dark mission-control theme lives in one module."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ThemeTests(unittest.TestCase):
    def test_theme_module_defines_palette_and_qss(self):
        from pdf_pro.ui.theme import ACCENT, BG, BORDER, MUTED, QSS, TEXT

        self.assertTrue(BG.lower().startswith("#"))
        self.assertTrue(TEXT.lower().startswith("#"))
        self.assertTrue(MUTED.lower().startswith("#"))
        self.assertTrue(ACCENT.lower().startswith("#"))
        self.assertTrue(BORDER.lower().startswith("#"))
        bg_int = int(BG.lstrip("#")[:6], 16)
        self.assertLess(bg_int, 0x202028)
        self.assertIn(ACCENT.lower(), QSS.lower())
        self.assertIn("QPushButton", QSS)
        self.assertIn("QToolBar", QSS)
        self.assertIn("QDialog", QSS)
        self.assertIn("QLineEdit", QSS)
        self.assertIn("QListWidget", QSS)
        self.assertIn("QTabWidget", QSS)
        self.assertIn("#primaryAction", QSS)

    def test_apply_theme_is_callable(self):
        from pdf_pro.ui.theme import apply_theme

        self.assertTrue(callable(apply_theme))

    def test_app_entry_applies_theme(self):
        text = (ROOT / "pdf_pro" / "app.py").read_text(encoding="utf-8")
        self.assertIn("apply_theme", text)

    def test_no_scattered_hex_stylesheets_in_ui(self):
        """Inline setStyleSheet with hex colors should not proliferate outside theme.py."""
        ui = ROOT / "pdf_pro" / "ui"
        offenders = []
        for path in ui.rglob("*.py"):
            if path.name == "theme.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = getattr(func, "attr", "") if isinstance(func, ast.Attribute) else ""
                if name != "setStyleSheet":
                    continue
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    if "#" in node.args[0].value:
                        offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
