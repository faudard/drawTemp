"""R2.C/R2.D: typed inspector, scoped references and Qt navigation gates."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.inspector_model import (
    InspectorError, common_value, edit_properties, preview_properties, shared_specs,
)
from drawtemp.studio.resource_links import (
    connections, reference_edges, resource_search,
)
from drawtemp.studio.workspace_model import Resource, resources


def session():
    return AuthoringSession.new(*reference_project())


def resource(editor, family, identifier):
    return next(item for item in resources(editor.snapshot())
                if item.family == family and item.resource_id == identifier)


class TypedInspectorTests(unittest.TestCase):
    def test_typed_fields_are_document_scoped(self):
        editor = session()
        mission = resource(editor, "maps", "r0_village_forest")
        keys = {spec.key for spec in shared_specs(editor.snapshot(), [mission])}
        self.assertTrue({"name", "reward", "target_ticks"} <= keys)
        gate = resource(editor, "objects", "gate")
        lever = resource(editor, "objects", "lever")
        self.assertIn("locked", {s.key for s in shared_specs(editor.snapshot(), [gate])})
        self.assertNotIn("locked", {s.key for s in shared_specs(editor.snapshot(), [lever])})
        self.assertEqual(
            {s.key for s in shared_specs(editor.snapshot(), [gate, lever])},
            {"name", "amount"})

    def test_actor_multi_edit_one_undo_and_original_ids(self):
        editor = session()
        actors = [item for item in resources(editor.snapshot())
                  if item.family == "actors"]
        before = editor.snapshot().to_dict()
        self.assertGreaterEqual(len(actors), 2)
        value, mixed = common_value(editor.snapshot(), actors[:2], "name")
        self.assertTrue(mixed)
        self.assertIsInstance(value, str)
        result = edit_properties(editor, actors[:2], {"attack": 15, "name": "Garde"})
        self.assertEqual(result.snapshot.revision, 1)
        data = editor.snapshot().to_dict()
        self.assertTrue(all(u["attack"] == 15 and u["name"] == "Garde"
                            for u in data["content"]["missions"][0]["units"][:2]))
        self.assertEqual(
            [u["id"] for u in data["content"]["missions"][0]["units"]],
            [u["id"] for u in before["content"]["missions"][0]["units"]])
        editor.undo()
        self.assertEqual(editor.snapshot().to_dict()["content"], before["content"])
        editor.redo()
        self.assertEqual(editor.snapshot().to_dict()["content"], data["content"])

    def test_door_types_and_atomic_validation(self):
        editor = session()
        gate = resource(editor, "objects", "gate")
        edit_properties(editor, [gate], {"locked": True, "hp": 7})
        row = editor.snapshot().to_dict()["content"]["missions"][0]["objects"][0]
        self.assertTrue(row["locked"])
        self.assertEqual(row["hp"], 7)
        prior = editor.snapshot().to_dict()
        for fields in ({"locked": "yes"}, {"hp": 0}, {"hp": 10001},
                       {"kind": "switch"}, {"name": "  "}):
            with self.subTest(fields=fields), self.assertRaises(InspectorError):
                edit_properties(editor, [gate], fields)
            self.assertEqual(editor.snapshot().to_dict(), prior)

    def test_stale_preview_and_selection_fail_closed(self):
        editor = session()
        mission = resource(editor, "maps", "r0_village_forest")
        revision = editor.revision
        preview = preview_properties(editor, [mission], {"reward": 250},
                                     expected_revision=revision)
        edit_properties(editor, [mission], {"target_ticks": 150})
        with self.assertRaisesRegex(ValueError, "stale"):
            editor.apply(preview)
        before = editor.snapshot().to_dict()
        with self.assertRaises(InspectorError):
            edit_properties(editor, [mission], {"reward": 200},
                            expected_revision=revision)
        with self.assertRaises(InspectorError):
            edit_properties(editor, [Resource("maps", "missing", "")],
                            {"reward": 200})
        with self.assertRaises(InspectorError):
            edit_properties(editor, [mission, mission], {"reward": 200})
        self.assertEqual(editor.snapshot().to_dict(), before)

    def test_project_and_scene_properties_are_canonical(self):
        editor = session()
        project = resource(editor, "project", "project")
        scene = resource(editor, "scenes", "arrival")
        edit_properties(editor, [project], {"title": "Jeanne — Studio"})
        edit_properties(editor, [scene], {"title": "Le départ"})
        state = editor.snapshot().to_dict()
        self.assertEqual(state["project"]["title"], "Jeanne — Studio")
        self.assertEqual(state["project"]["story"]["scenes"][0]["title"], "Le départ")
        editor.undo()
        self.assertNotEqual(editor.snapshot().to_dict()["project"]["story"]["scenes"][0]["title"],
                            "Le départ")


class ReferenceGraphTests(unittest.TestCase):
    def test_object_reference_is_typed_and_mission_scoped(self):
        editor = session()
        gate = resource(editor, "objects", "gate")
        lever = resource(editor, "objects", "lever")
        incoming = connections(editor.snapshot(), [gate], "incoming")
        self.assertTrue(any(edge.source.key == lever.key and edge.field == "link"
                            for edge in incoming))
        outgoing = connections(editor.snapshot(), [lever], "outgoing")
        self.assertTrue(any(edge.target.key == gate.key for edge in outgoing))
        self.assertEqual(connections(editor.snapshot(), [], "incoming"), ())

    def test_duplicate_ids_in_other_missions_do_not_leak_links(self):
        editor = session()
        pair = editor.snapshot().to_dict()
        from copy import deepcopy
        second = deepcopy(pair["content"]["missions"][0])
        second["id"] = "second"
        pair["content"]["missions"].append(second)
        edges = [edge for edge in reference_edges(pair) if edge.field == "link"]
        self.assertEqual(len(edges), 2)
        self.assertEqual({edge.source.mission_id for edge in edges},
                         {"r0_village_forest", "second"})
        for edge in edges:
            self.assertEqual(edge.source.mission_id, edge.target.mission_id)

    def test_entry_scene_and_search_facets(self):
        editor = session()
        scene = resource(editor, "scenes", "arrival")
        project = resource(editor, "project", "project")
        self.assertTrue(any(edge.target.key == scene.key
                            for edge in connections(editor.snapshot(),
                                                    [project], "outgoing")))
        self.assertEqual(
            resource_search(editor.snapshot(), families=("objects",),
                            mission_id="r0_village_forest", query="gate")[0].resource_id,
            "gate")
        results = resource_search(editor.snapshot(), favorites={scene.key})
        self.assertEqual([row.key for row in results], [scene.key])
        referenced = resource_search(editor.snapshot(), uses=[project])
        self.assertTrue(any(row.key == scene.key for row in referenced))

    def test_no_ui_imports_for_both_models(self):
        import subprocess
        import sys
        code = """
import sys
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PySide6', 'tkinter'):
            raise AssertionError('Unexpected UI import')
sys.meta_path.insert(0, Guard())
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.inspector_model import shared_specs
from drawtemp.studio.resource_links import reference_edges
s = AuthoringSession.new(*reference_project())
assert reference_edges(s.snapshot())
"""
        subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, check=True)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 missing")
class QtInspectorExplorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, folder):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        settings = QSettings(str(Path(folder) / "studio.ini"), QSettings.IniFormat)
        return StudioWindow(session(), settings=settings)

    def test_typed_widgets_commit_and_inline_error(self):
        with tempfile.TemporaryDirectory() as folder:
            win = self._window(folder)
            actor = next(r for r in resources(win.session.snapshot()) if r.family == "actors")
            self.assertTrue(win.focus_resource(actor.key))
            editor = win.property_widgets["attack"][0]
            self.assertEqual(editor.__class__.__name__, "QSpinBox")
            editor.setValue(17)
            win.apply_selection()
            self.assertEqual(win.session.revision, 1)
            self.assertEqual(win.inspector_error.text(), "")
            assert win.focus_resource(actor.key)
            name = win.property_widgets["name"][0]
            name.setText("")
            name.textEdited.emit("")
            win.apply_selection()
            self.assertEqual(win.session.revision, 1)
            self.assertNotEqual(win.inspector_error.text(), "")
            # Reset the dirty transaction so offscreen CI never prompts for
            # an interactive Save / Discard choice during window close.
            win.session.undo()
            win.refresh()
            win.close()

    def test_reference_navigation_and_facets(self):
        with tempfile.TemporaryDirectory() as folder:
            win = self._window(folder)
            gate = resource(win.session, "objects", "gate")
            lever = resource(win.session, "objects", "lever")
            self.assertTrue(win.focus_resource(gate.key))
            self.assertTrue(win.links.count() > 0)
            self.assertTrue(win.focus_resource(lever.key))
            link = next(win.links.item(i) for i in range(win.links.count())
                        if win.links.item(i).data(256) == gate.key)
            win.follow_reference(link)
            self.assertEqual(win._selected[0].key, gate.key)
            win.reference_filter.setCurrentIndex(1)
            self.assertIn(lever.key, win.proxy.related_keys)
            self.assertTrue(win.focus_resource(lever.key))
            win.toggle_favorite()
            self.assertIn(win._identity(lever), win._favorites())
            win.family_filter.setCurrentIndex(win.family_filter.findData("objects"))
            self.assertEqual(win.proxy.family_filter, "objects")
            win.close()


if __name__ == "__main__":
    unittest.main()
