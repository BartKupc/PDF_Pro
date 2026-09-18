"""Export after preview: no silent failures; save-path logic is offscreen-testable."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from pdf_pro.export import ExportError

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "pdf_pro" / "ui" / "main_window.py"


def _export_flow_node() -> ast.FunctionDef:
    tree = ast.parse(MAIN.read_text(encoding="utf-8"), filename=str(MAIN))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "export_flow":
                    return item
    raise AssertionError("MainWindow.export_flow not found")


def _is_save_dialog_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    names = []
    if isinstance(func, ast.Name):
        names.append(func.id)
    elif isinstance(func, ast.Attribute):
        names.append(func.attr)
    return any(
        n in {"getSaveFileName", "get_save_file_name"} for n in names
    )


def _try_nodes(fn: ast.FunctionDef) -> list[ast.Try]:
    return [n for n in ast.walk(fn) if isinstance(n, ast.Try)]


class ExportFlowStructureTests(unittest.TestCase):
    def test_save_dialog_call_is_inside_try(self):
        fn = _export_flow_node()
        dialogs = [n for n in ast.walk(fn) if _is_save_dialog_call(n)]
        self.assertTrue(dialogs, "export_flow must call a save-file dialog")
        covered = False
        for try_node in _try_nodes(fn):
            inner = [n for n in ast.walk(try_node) if _is_save_dialog_call(n)]
            if inner:
                covered = True
                break
        self.assertTrue(covered, "save dialog must sit inside try/except")

    def test_unexpected_exception_handler_present(self):
        fn = _export_flow_node()
        found = False
        for try_node in _try_nodes(fn):
            for handler in try_node.handlers:
                t = handler.type
                if t is None:
                    found = True
                elif isinstance(t, ast.Name) and t.id == "Exception":
                    found = True
        self.assertTrue(found, "export_flow must catch unexpected Exception")

    def test_no_toplevel_save_dialog_outside_try(self):
        fn = _export_flow_node()
        for stmt in fn.body:
            if isinstance(stmt, ast.Try):
                continue
            for n in ast.walk(stmt):
                self.assertFalse(
                    _is_save_dialog_call(n),
                    "save dialog at export_flow top level (outside try)",
                )


class CompleteExportTests(unittest.TestCase):
    def test_cancelled_save_is_explicit(self):
        from pdf_pro.export_session import complete_export

        result = complete_export(
            Path("/tmp/src.pdf"),
            overlay=None,
            dest=None,
            export_fn=lambda *a, **k: None,
            assert_fn=lambda s, d: d,
        )
        self.assertTrue(result.cancelled)
        self.assertIsNone(result.path)

    def test_success_message_includes_full_path(self):
        from pdf_pro.export_session import complete_export

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "doc.pdf"
            dest = Path(tmp) / "out.pdf"
            src.write_bytes(b"%PDF-1.4\n")
            called = {}

            def export_fn(source, overlay, dest_path, password=None):
                called["dest"] = dest_path
                dest_path.write_bytes(b"%PDF-1.4\n")

            result = complete_export(
                src,
                overlay=object(),
                dest=dest,
                export_fn=export_fn,
                assert_fn=lambda s, d: d,
                source_sha=None,
            )
            self.assertFalse(result.cancelled)
            self.assertEqual(result.path, dest)
            self.assertIn(str(dest), result.message)
            self.assertEqual(called["dest"], dest)

    def test_assert_failure_propagates(self):
        from pdf_pro.export_session import complete_export

        def boom(source, dest):
            raise ExportError(f"Refusing to overwrite the source PDF.\\nPath: {dest}")

        with self.assertRaises(ExportError):
            complete_export(
                Path("/tmp/a.pdf"),
                overlay=None,
                dest=Path("/tmp/a.pdf"),
                export_fn=lambda *a, **k: None,
                assert_fn=boom,
            )

    def test_verify_failure_raises(self):
        from pdf_pro.export_session import complete_export

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "doc.pdf"
            dest = Path(tmp) / "out.pdf"
            src.write_bytes(b"%PDF-1.4\n")
            with self.assertRaises(ExportError) as ctx:
                complete_export(
                    src,
                    overlay=object(),
                    dest=dest,
                    export_fn=lambda *a, **k: dest.write_bytes(b"x"),
                    assert_fn=lambda s, d: d,
                    source_sha="deadbeef",
                    verify_fn=lambda path, sha: False,
                )
            self.assertIn("checksum", str(ctx.exception).lower())

    def test_open_containing_folder_uses_parent(self):
        from pdf_pro.export_session import open_containing_folder

        seen = []
        dest = Path("/tmp/exports/out.pdf")
        open_containing_folder(dest, opener=seen.append)
        self.assertEqual(seen, [str(dest.parent)])


class FileDialogPolicyTests(unittest.TestCase):
    def test_all_file_dialogs_are_non_native(self):
        ui = ROOT / "pdf_pro"
        offenders = []
        for path in ui.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "getSaveFileName" not in text and "getOpenFileName" not in text:
                continue
            if path.name == "file_dialogs.py":
                self.assertIn("DontUseNativeDialog", text)
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if "getSaveFileName" in line or "getOpenFileName" in line:
                    offenders.append(f"{path.name}:{i}:{line.strip()}")
        self.assertEqual(
            offenders,
            [],
            "call QFileDialog only via pdf_pro.ui.file_dialogs (non-native)",
        )


if __name__ == "__main__":
    unittest.main()
