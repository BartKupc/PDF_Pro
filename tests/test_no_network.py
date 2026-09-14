"""Fail if the application package grows network clients."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

FORBIDDEN = {
    "socket",
    "http.client",
    "urllib.request",
    "urllib.client",
    "requests",
    "httpx",
    "aiohttp",
}


class NoNetworkTests(unittest.TestCase):
    def test_no_network_imports_in_pdf_pro(self):
        root = Path(__file__).resolve().parents[1] / "pdf_pro"
        offenders = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                    full = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module.split(".")[0]]
                    full = [node.module]
                else:
                    continue
                for n, f in zip(names, full):
                    if n in FORBIDDEN or f in FORBIDDEN:
                        offenders.append(f"{path.name}: {f}")
        self.assertEqual(offenders, [])
