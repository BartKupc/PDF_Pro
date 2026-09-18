"""M2 UI wiring: document tabs, Pages ribbon, no inline styles."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class M2UiStructureTests(unittest.TestCase):
    def test_main_window_has_document_tabs(self):
        text = (ROOT / "pdf_pro" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("QTabWidget", text)
        self.assertIn("docTabs", text)
        self.assertIn("DocumentPane", text)
        self.assertIn("DocumentSession", text)

    def test_no_inline_hex_stylesheets_outside_theme(self):
        ui = ROOT / "pdf_pro" / "ui"
        offenders = []
        for path in ui.rglob("*.py"):
            if path.name == "theme.py":
                continue
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "setStyleSheet" in line and "#" in line:
                    offenders.append(f"{path.name}:{i}:{line.strip()}")
        self.assertEqual(offenders, [])

    def test_preview_uses_worker(self):
        text = (ROOT / "pdf_pro" / "ui" / "preview.py").read_text(encoding="utf-8")
        self.assertIn("PreviewWorker", text)
        self.assertIn("QProgressBar", text)


if __name__ == "__main__":
    unittest.main()
