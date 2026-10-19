"""R18.B: atomic multi-edit drafts, stale-session UX and contextual commands."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.inspector_model import (
    InspectorError, common_value, edit_properties, validate_draft,
)
from drawtemp.studio.r18_context import ContextCommandError, require_context
from drawtemp.studio.workspace_model import resources


def session():
    return AuthoringSession.new(*reference_project())


class ContextPolicyTests(unittest.TestCase):
    def test_map_commands_refused_in_construction(self):
        commands = (
            "map.create", "map.duplicate", "map.rename", "map.copy",
            "map.paste", "map.stroke", "map.transform",
            "map.apply_transform", "map.objective",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(require_context("map", command))
                with self.assertRaises(ContextCommandError):
                    require_context("construction", command)

    def test_construction_commands_refused_in_map(self):
        commands = (
            "construction.select", "construction.edit",
            "construction.history", "construction.level", "construction.view",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(require_context("construction", command))
                with self.assertRaises(ContextCommandError):
                    require_context("map", command)
        with self.assertRaises(ContextCommandError):
            require_context("map", "unknown")

    def test_policies_do_not_import_ui_modules(self):
        code = (
            "import sys; from drawtemp.studio.r18_context import require_context; "
            "from drawtemp.studio.inspector_model import validate_draft; "
            "assert require_context('map','map.stroke'); "
            "assert 'PySide6' not in sys.modules; "
            "assert 'tkinter' not in sys.modules"
        )
        subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, check=True)


class DraftModelTests(unittest.TestCase):
    def test_invalid_multi_draft_is_reversible_and_atomic(self):
        editor = session()
        actors = [r for r in resources(editor.snapshot()) if r.family == "actors"][:2]
        self.assertEqual(len(actors), 2)
        before = editor.snapshot().to_dict()
        value, mixed = common_value(editor.snapshot(), actors, "name")
        self.assertTrue(mixed)
        self.assertIsInstance(value, str)
        typed, errors = validate_draft(
            editor.snapshot(), actors, {
                "name": "   ", "attack": 23, "speed": True,
            })
        self.assertEqual(typed, {"attack": 23})
        self.assertEqual(set(errors), {"name", "speed"})
        self.assertEqual(editor.snapshot().to_dict(), before)
        transition = edit_properties(editor, actors,
                                     {"name": "Sentinelle", "attack": 23})
        self.assertEqual(transition.snapshot.revision, 1)
        updated = editor.snapshot().to_dict()["content"]["missions"][0]["units"]
        self.assertTrue(all(actor["name"] == "Sentinelle" and
                            actor["attack"] == 23 for actor in updated[:2]))
        self.assertEqual([row["id"] for row in updated],
                         [row["id"] for row in before["content"]["missions"][0]["units"]])
        editor.undo()
        self.assertEqual(editor.snapshot().to_dict()["content"], before["content"])

    def test_draft_disallows_nonshared_or_duplicate_selection(self):
        editor = session()
        chosen = [r for r in resources(editor.snapshot()) if r.family == "actors"][:2]
        typed, errors = validate_draft(editor.snapshot(), chosen, {"locked": True})
        self.assertEqual(typed, {})
        self.assertIn("locked", errors)
        with self.assertRaises(InspectorError):
            validate_draft(editor.snapshot(), chosen[:1] * 2, {"name": "Dup"})


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class InspectorQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def window(self, folder):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        setting = QSettings(str(Path(folder) / "studio.ini"),
                           QSettings.IniFormat)
        return StudioWindow(session(), settings=setting)

    def test_invalid_field_shows_immediately_and_discard_restores(self):
        with tempfile.TemporaryDirectory() as folder:
            window = self.window(folder)
            try:
                actor = next(r for r in resources(window.session.snapshot())
                             if r.family == "actors")
                self.assertTrue(window.focus_resource(actor.key))
                original = window.property_widgets["name"][0].text()
                field = window.property_widgets["name"][0]
                field.setText("")
                field.textEdited.emit("")
                self.assertFalse(window.apply_button.isEnabled())
                self.assertTrue(window.discard_button.isEnabled())
                self.assertTrue(window._property_error_labels["name"].text())
                self.assertTrue(window.inspector_error.text())
                self.assertEqual(window.session.revision, 0)
                window.discard_inspector_changes()
                self.assertEqual(window.property_widgets["name"][0].text(),
                                 original)
                self.assertFalse(window.discard_button.isEnabled())
            finally:
                window.close()

    def test_mixed_multi_edit_commits_in_one_undo(self):
        from PySide6.QtCore import QItemSelectionModel, Qt
        with tempfile.TemporaryDirectory() as folder:
            window = self.window(folder)
            try:
                actors = [r for r in resources(window.session.snapshot())
                          if r.family == "actors"][:2]
                self.assertTrue(window.focus_resource(actors[0].key))
                for row in range(window.resource_model.rowCount()):
                    parent = window.resource_model.item(row)
                    for i in range(parent.rowCount()):
                        item = parent.child(i)
                        if tuple(item.data(Qt.UserRole).split("|", 2)) == actors[1].key:
                            index = window.proxy.mapFromSource(item.index())
                            window.resource_view.selectionModel().select(
                                index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
                self.assertEqual(len(window._selected), 2)
                field = window.property_widgets["name"][0]
                self.assertEqual(field.placeholderText(), "Valeurs multiples")
                field.setText("Sentinelles")
                field.textEdited.emit("Sentinelles")
                self.assertTrue(window.apply_button.isEnabled())
                self.assertTrue(window.apply_selection())
                self.assertEqual(window.session.revision, 1)
                names = [unit["name"] for unit in
                         window.session.snapshot().to_dict()["content"]["missions"][0]["units"][:2]]
                self.assertEqual(names, ["Sentinelles", "Sentinelles"])
                window.session.undo()
                window.refresh()
            finally:
                window.close()

    def test_external_revision_keeps_draft_visible_but_blocks_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            window = self.window(folder)
            try:
                actor = next(r for r in resources(window.session.snapshot())
                             if r.family == "actors")
                self.assertTrue(window.focus_resource(actor.key))
                field = window.property_widgets["attack"][0]
                field.setValue(333)
                self.assertTrue(window.apply_button.isEnabled())
                edit_properties(window.session, [actor], {"speed": 12})
                window._refresh_if_changed()
                self.assertEqual(field.value(), 333)
                self.assertFalse(window.apply_button.isEnabled())
                self.assertIn("changé", window.inspector_error.text())
                self.assertFalse(window.apply_selection())
                window.discard_inspector_changes()
                self.assertFalse(window.inspector_error.text())
                window.session.undo()
                window.refresh()
            finally:
                window.close()

    @unittest.skipUnless(
        os.environ.get("DRAWTEMP_R18B_MAP_GUI") == "1",
        "Requires Qt Quick renderer and software offscreen backend")
    def test_real_map_construction_switch_disables_paint_and_keeps_session(self):
        with tempfile.TemporaryDirectory() as folder:
            window = self.window(folder)
            try:
                original = window.session
                window.navigate("construction")
                map_window = window._models["maps"]
                self.assertIs(map_window.studio.authoring, original)
                self.assertIs(map_window.construction.workspace.authoring, original)
                self.assertEqual(map_window.mode.currentIndex(), 1)
                self.assertFalse(map_window.toolbar_actions["Copier"].isEnabled())
                self.assertFalse(map_window.tools.isEnabled())
                previous = original.revision
                map_window.begin_stroke(1, 1)
                map_window.finish_stroke(3, 3)
                self.assertEqual(original.revision, previous)
                self.assertEqual(map_window.stroke, [])
                window.navigate("maps")
                self.assertEqual(map_window.mode.currentIndex(), 0)
                self.assertTrue(map_window.toolbar_actions["Copier"].isEnabled())
                self.assertTrue(map_window.tools.isEnabled())
                self.assertIs(window._models["maps"], map_window)
            finally:
                window.close()

    def test_construction_dock_refuses_delayed_mutation_outside_mode(self):
        from drawtemp.sdk.construction import ConstructionWorkspace
        from drawtemp.studio.construction_dock import ConstructionDock
        with tempfile.TemporaryDirectory():
            editor = session()
            start = editor.revision
            dock = ConstructionDock(ConstructionWorkspace(
                editor, "r0_village_forest"))
            dock.context_enabled = lambda: False
            calls = []
            self.assertIsNone(dock._apply(lambda: calls.append("mutate")))
            self.assertIsNone(dock._history(lambda: calls.append("undo")))
            dock.on_renderer_hit("gate", (1, 1), (1, 1), "facade")
            self.assertEqual(calls, [])
            self.assertEqual(editor.revision, start)
            dock.close()


if __name__ == "__main__":
    unittest.main()
