"""Extract must not compose/save on the UI thread."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "pdf_pro" / "ui" / "main_window.py"


def _method_node(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    return item
    raise AssertionError(f"MainWindow.{name} not found")


class ExtractOffThreadTests(unittest.TestCase):
    def test_page_extract_uses_export_worker(self):
        fn = _method_node(MAIN, "_page_extract")
        names: set[str] = set()
        nested: list[ast.FunctionDef] = []
        for node in ast.walk(fn):
            if isinstance(node, ast.Name):
                names.add(node.id)
            if isinstance(node, ast.FunctionDef) and node is not fn:
                nested.append(node)
        self.assertIn("ExportWorker", names)
        self.assertIn("QProgressDialog", names)
        nested_names: set[str] = set()
        for inner in nested:
            for node in ast.walk(inner):
                if isinstance(node, ast.Name):
                    nested_names.add(node.id)
        self.assertIn(
            "write_plan_pdf",
            nested_names,
            "write_plan_pdf must run inside the ExportWorker callback, not on the UI thread",
        )
        top_calls = []
        for node in fn.body:
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func = child.func
                    if isinstance(func, ast.Name) and func.id == "write_plan_pdf":
                        top_calls.append(child)
                    if isinstance(func, ast.Attribute) and func.attr == "write_plan_pdf":
                        # attribute form compose.write_plan_pdf
                        if not any(isinstance(p, ast.FunctionDef) for p in ast.walk(fn) if p is not fn):
                            top_calls.append(child)
        self.assertEqual(
            [],
            [c.lineno for c in top_calls if not _inside_nested(c, nested)],
            "write_plan_pdf must not be called at MainWindow._page_extract top level",
        )


def _inside_nested(node: ast.AST, nested: list[ast.FunctionDef]) -> bool:
    for inner in nested:
        for child in ast.walk(inner):
            if child is node:
                return True
    return False


if __name__ == "__main__":
    unittest.main()
