"""Desktop launch files for .deb / AppImage / manual install."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "packaging" / "linux" / "pdf-pro.desktop"
EXAMPLE = ROOT / "pdf-pro.desktop.example"
BUILD_SH = ROOT / "packaging" / "linux" / "build.sh"


class DesktopLaunchTests(unittest.TestCase):
    def test_packaged_desktop_file_keys(self):
        text = DESKTOP.read_text(encoding="utf-8")
        self.assertIn("[Desktop Entry]", text)
        self.assertIn("Type=Application", text)
        self.assertIn("Name=PDF_Pro", text)
        self.assertRegex(text, r"(?m)^Exec=.+")
        self.assertRegex(text, r"(?m)^Icon=.+")
        self.assertIn("Terminal=false", text)
        self.assertIn("Categories=", text)

    def test_example_desktop_file_exists_for_manual_install(self):
        self.assertTrue(EXAMPLE.is_file(), "ship pdf-pro.desktop.example at repo root")
        text = EXAMPLE.read_text(encoding="utf-8")
        self.assertIn("[Desktop Entry]", text)
        self.assertIn("Type=Application", text)
        self.assertIn("Exec=", text)

    def test_build_sh_runs_desktop_file_validate(self):
        text = BUILD_SH.read_text(encoding="utf-8")
        self.assertIn("desktop-file-validate", text)
        self.assertIn("usr/share/applications/pdf-pro.desktop", text)

    def test_desktop_file_validate_if_installed(self):
        tool = shutil.which("desktop-file-validate")
        if not tool:
            self.skipTest("desktop-file-validate not installed")
        for path in (DESKTOP, EXAMPLE):
            proc = subprocess.run([tool, str(path)], capture_output=True, text=True)
            self.assertEqual(
                proc.returncode,
                0,
                f"{path.name} failed desktop-file-validate:\n{proc.stdout}{proc.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
