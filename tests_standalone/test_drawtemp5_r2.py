"""R2: headless transaction and optional offscreen Qt shell smoke tests."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.workspace_model import (
    Resource, common_name, edit_names, editable_name, reference_hints, resources,
)


def session():
    return AuthoringSession.new(*reference_project())


class ResourceAndInspectorTests(unittest.TestCase):
    def test_projection_has_stable_keys_and_jeanne(self):
        rows = resources(session().snapshot())
        self.assertEqual(len({row.key for row in rows}), len(rows))
        self.assertTrue(any(row.family == "maps" for row in rows))
        self.assertTrue(any(row.family == "actors" for row in rows))
        self.assertTrue(any(row.family == "objects" and row.resource_id == "lever"
                            for row in rows))
        self.assertTrue(any(row.family == "project" for row in rows))

    def test_inspector_edits_can_undo_and_redo_without_touching_ids(self):
        editor = session()
        mission = next(r for r in resources(editor.snapshot()) if r.family == "maps")
        before = editor.snapshot().to_dict()
        result = edit_names(editor, [mission], "Village remis à neuf")
        self.assertEqual(result.snapshot.revision, 1)
        changed = editor.snapshot().to_dict()
        self.assertEqual(changed["content"]["missions"][0]["name"], "Village remis à neuf")
        self.assertEqual(changed["content"]["missions"][0]["id"],
                         before["content"]["missions"][0]["id"])
        self.assertEqual(changed["project"], before["project"])
        editor.undo()
        self.assertEqual(editor.snapshot().to_dict()["content"], before["content"])
        editor.redo()
        self.assertEqual(editor.snapshot().to_dict()["content"], changed["content"])

    def test_multi_selection_is_atomic(self):
        editor = session()
        selected = [r for r in resources(editor.snapshot())
                    if r.family == "objects" and r.resource_id in ("lever", "gate")]
        self.assertEqual(len(selected), 2)
        first, mixed = common_name(selected)
        self.assertIsInstance(first, str)
        self.assertIsInstance(mixed, bool)
        edit_names(editor, selected, "Éléments du portail")
        names = [r.title for r in resources(editor.snapshot())
                 if r.family == "objects" and r.resource_id in ("lever", "gate")]
        self.assertEqual(names, ["Éléments du portail"] * 2)
        self.assertEqual(editor.revision, 1)
        editor.undo()
        self.assertNotEqual(
            [r.title for r in resources(editor.snapshot())
             if r.family == "objects" and r.resource_id in ("lever", "gate")], names)

    def test_invalid_and_stale_selection_fails_closed(self):
        editor = session()
        before = editor.snapshot().to_dict()
        with self.assertRaises(ValueError):
            edit_names(editor, [Resource("project", "project", "P")], "Wrong")
        with self.assertRaises(ValueError):
            edit_names(editor, [Resource("maps", "missing", "Missing")], "Wrong")
        with self.assertRaises(ValueError):
            edit_names(editor, [Resource("maps", "r0_village_forest", "Test")], " ")
        self.assertEqual(editor.snapshot().to_dict(), before)
        self.assertFalse(editable_name([Resource("campaigns", "main", "Main")]))

    def test_reference_hint_is_advisory_only(self):
        editor = session()
        obj = next(r for r in resources(editor.snapshot()) if r.resource_id == "gate")
        paths = reference_hints(editor.snapshot(), obj)
        self.assertTrue(any("link" in path for path in paths))
        self.assertEqual(editor.revision, 0)

    def test_game_sdk_does_not_import_qt_from_model(self):
        script = """
import sys
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PySide6', 'tkinter'):
            raise AssertionError('UI dependency: ' + fullname)
sys.meta_path.insert(0, Guard())
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.workspace_model import resources
assert any(r.family == 'maps' for r in resources(
    AuthoringSession.new(*reference_project()).snapshot()))
"""
        subprocess.run([sys.executable, "-c", script], check=True,
                       capture_output=True, text=True)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class QtShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_shell_docks_command_palette_and_settings(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(Path(folder) / "studio.ini"),
                                 QSettings.IniFormat)
            window = StudioWindow(session(), settings=settings)
            self.assertEqual(window.workspace_tabs.currentWidget(),
                             window.pages["project"])
            self.assertEqual(window.resource_dock.objectName(), "r2-resource-dock")
            self.assertIn("palette", window.commands)
            self.assertGreater(window.resource_model.rowCount(), 2)
            window.navigate("analysis")
            self.assertEqual(window.workspace_tabs.currentWidget(),
                             window.pages["analysis"])
            window.layout_preset("compact")
            self.assertFalse(window.inspector_dock.isVisible())
            window.set_theme("light")
            self.assertEqual(settings.value("theme"), "light")
            window.close()
            self.assertIsNotNone(settings.value("window/docks"))

    def test_workspace_switcher_and_grouped_tools_remain_accessible(self):
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QMenu
        from drawtemp.studio.qt_shell import StudioWindow
        from drawtemp.studio.r18_navigation import WORKSPACES
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(Path(folder) / "studio.ini"),
                                 QSettings.IniFormat)
            window = StudioWindow(session(), settings=settings)
            try:
                window.resize(900, 650)
                window.show()
                self.app.processEvents()
                self.assertTrue(window.workspace_switcher.isVisible())
                self.assertEqual(
                    window.toolbar_workspaces_menu.actions(),
                    [window.commands["go_" + key] for key in WORKSPACES])
                self.assertEqual(set(window._toolbar_buttons),
                                 {"project", "gameplay", "maps",
                                  "actors", "events", "campaigns"})
                tools_action = next(action for action in
                                    window.menuBar().actions()
                                    if action.text().replace("&", "") == "Outils")
                tools_menu = tools_action.menu()
                self.assertLessEqual(len(tools_menu.actions()), 14)
                self.assertTrue(any(action.menu() and
                                    action.menu().title() == "Gameplay, combat et IA"
                                    for action in tools_menu.actions()))
                def included(menu):
                    found = []
                    for action in menu.actions():
                        found.append(action)
                        if action.menu() is not None:
                            found.extend(included(action.menu()))
                    return found
                all_actions = included(tools_menu)
                for key in ("r31_logic", "r38_preflight", "r43_ability",
                            "r77_lab", "r30_creator", "r57_translation",
                            "r76_bench"):
                    self.assertIn(window.commands[key], all_actions)
                self.assertTrue(any(
                    action.objectName() == "r56-qa-lab-action"
                    for action in all_actions))
                self.assertEqual(
                    window.commands["r31_logic"].text(),
                    "Logique visuelle et événements…")
                self.assertIn("R31", window.commands["r31_logic"].toolTip())
                window.set_language("en")
                self.assertEqual(window._toolbar_buttons["maps"].text(), "Map")
                self.assertIn("All workspaces", window.workspace_switcher.text())
                self.assertEqual(window.commands["go_maps"].text(), "Workspace: Map")
            finally:
                window.close()

    def test_shell_native_database_uses_same_session(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(Path(folder) / "studio.ini"),
                                 QSettings.IniFormat)
            source = session()
            window = StudioWindow(source, settings=settings)
            window.navigate("database")
            self.assertIs(window._models["database"].editor.session, source)
            window.navigate("actors")
            self.assertIs(window.pages["actors"], window.pages["database"])
            window.close()


if __name__ == "__main__":
    unittest.main()
