"""Ribbon layout: locked tab grouping, no lost actions, shortcuts intact."""

from __future__ import annotations

import os
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class RibbonSpecTests(unittest.TestCase):
    def test_tab_order_is_home_amend_sign_export(self):
        from pdf_pro.ribbon_spec import TAB_ORDER

        self.assertEqual(list(TAB_ORDER), ["Home", "Amend", "Sign", "Export"])

    def test_every_action_lives_in_exactly_one_tab(self):
        from pdf_pro.ribbon_spec import ACTIONS

        seen = defaultdict(list)
        for aid, (tab, _group, _label) in ACTIONS.items():
            seen[aid].append(tab)
        dupes = {aid: tabs for aid, tabs in seen.items() if len(tabs) != 1}
        self.assertEqual(dupes, {}, "action ids must appear in exactly one tab")

    def test_legacy_toolbar_actions_all_present(self):
        from pdf_pro.ribbon_spec import ACTIONS, LEGACY_TOOLBAR_ACTIONS

        missing = sorted(LEGACY_TOOLBAR_ACTIONS - set(ACTIONS))
        self.assertEqual(missing, [], "v0.1.3 toolbar actions must survive on the ribbon")

    def test_locked_home_grouping(self):
        from pdf_pro.ribbon_spec import actions_in

        home = actions_in("Home")
        for aid in (
            "open",
            "prev",
            "next",
            "page_label",
            "zoom_out",
            "zoom_in",
            "fit_width",
            "fit_page",
            "rotate_view",
        ):
            self.assertIn(aid, home)

    def test_locked_amend_grouping(self):
        from pdf_pro.ribbon_spec import actions_in

        amend = actions_in("Amend")
        for aid in (
            "add_text",
            "cover_replace",
            "whiteout",
            "insert_image",
            "undo",
            "redo",
        ):
            self.assertIn(aid, amend)

    def test_locked_sign_grouping(self):
        from pdf_pro.ribbon_spec import actions_in

        sign = actions_in("Sign")
        for aid in (
            "draw_signature",
            "type_signature",
            "upload_signature",
            "vault",
            "place_initials",
        ):
            self.assertIn(aid, sign)

    def test_locked_export_grouping(self):
        from pdf_pro.ribbon_spec import actions_in

        export = actions_in("Export")
        self.assertEqual(export, {"preview_export"})

    def test_shortcut_registry(self):
        from pdf_pro.ribbon_spec import SHORTCUTS

        self.assertEqual(SHORTCUTS["preview_export"], "Ctrl+E")
        self.assertEqual(SHORTCUTS["open"], "Ctrl+O")
        self.assertEqual(SHORTCUTS["undo"], "Ctrl+Z")
        self.assertEqual(SHORTCUTS["redo"], "Ctrl+Shift+Z")
        self.assertEqual(SHORTCUTS["zoom_in"], "Ctrl+=")
        self.assertEqual(SHORTCUTS["zoom_out"], "Ctrl+-")
        self.assertEqual(SHORTCUTS["delete"], "Delete")

    def test_main_window_registers_shortcuts(self):
        text = (ROOT / "pdf_pro" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("SHORTCUTS", text)
        self.assertIn("QKeySequence", text)
        self.assertIn("_install_shortcuts", text)
        self.assertIn("preview_export", text)

    def test_main_window_uses_ribbon_not_single_toolbar(self):
        text = (ROOT / "pdf_pro" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("_build_ribbon", text)
        self.assertNotIn('QToolBar("Main")', text)
        self.assertNotIn("addToolBar", text)


def _qt_available() -> bool:
    try:
        import PySide6.QtWidgets  # noqa: F401

        return True
    except Exception:
        return False


class RibbonWidgetTests(unittest.TestCase):
    @unittest.skipUnless(_qt_available(), "PySide6 not installed")
    def test_ribbon_builds_four_tabs_and_fits_width(self):
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QLabel,
            QSpinBox,
        )

        from pdf_pro.ribbon_spec import ACTIONS, TAB_ORDER
        from pdf_pro.ui.ribbon import RibbonBar

        app = QApplication.instance() or QApplication([])
        extras = {
            "page_label": QLabel(" 1 / 1 "),
            "font": QComboBox(),
            "size": QSpinBox(),
            "bold": QCheckBox("Bold"),
            "colour": QLabel("Colour"),
        }
        bar = RibbonBar()
        bar.populate(ACTIONS, extras)
        self.assertEqual(bar.count(), 4)
        self.assertEqual([bar.tabText(i) for i in range(bar.count())], list(TAB_ORDER))
        self.assertLessEqual(bar.maximumHeight(), 110)
        self.assertGreaterEqual(bar.minimumHeight(), 90)
        for aid in ACTIONS:
            self.assertIn(aid, bar.widgets)
        bar.resize(1366, bar.maximumHeight())
        hint = bar.sizeHint()
        self.assertLessEqual(hint.width(), 1366, "ribbon must fit 1366px without overflow")
        app

    @unittest.skipUnless(_qt_available(), "PySide6 not installed")
    def test_export_button_is_primary(self):
        from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel, QSpinBox

        from pdf_pro.ribbon_spec import ACTIONS
        from pdf_pro.ui.ribbon import RibbonBar

        app = QApplication.instance() or QApplication([])
        extras = {
            "page_label": QLabel("—"),
            "font": QComboBox(),
            "size": QSpinBox(),
            "bold": QCheckBox("Bold"),
            "colour": QLabel("Colour"),
        }
        bar = RibbonBar()
        bar.populate(ACTIONS, extras)
        btn = bar.widgets["preview_export"]
        self.assertEqual(btn.objectName(), "primaryAction")
        app


if __name__ == "__main__":
    unittest.main()
