"""R49.B2 inspector integrity and non-destructive edit lifetime tests."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.studio.r49_inspector_integrity import (
    ReferenceAudit, ReferenceProblem, problems_for_selection, reference_audit,
)
from drawtemp.studio.workspace_model import resources


def pair_fixture():
    return {
        "content": {"missions": [
            {"id": "village", "name": "Village", "next_missions": ["forest"],
             "units": [{"id": "guard", "name": "Guard", "object_id": "door"}],
             "objects": [{"id": "door", "name": "Door", "kind": "door"}],
             "triggers": [{"id": "lever", "name": "Lever", "link": "door"}]},
            {"id": "forest", "name": "Forest", "next_missions": [],
             "units": [{"id": "guard", "name": "Forest Guard"}],
             "objects": [], "triggers": []},
        ]},
        "project": {"title": "Test", "campaigns": [], "cinematics": [],
                    "story": {"entry_scenes": {"intro": "start"},
                              "scenes": [{"id": "start", "title": "Start",
                                          "next_scene": ""}]}},
    }


class R49ReferenceIntegrityTests(unittest.TestCase):
    def test_valid_local_links_and_existing_targets_are_clean(self):
        original = pair_fixture()
        self.assertTrue(reference_audit(original).passed)
        self.assertEqual(reference_audit(original).problems, ())
        self.assertEqual(reference_audit(original).scanned_nodes > 0, True)

    def test_missing_references_are_typed_and_source_navigable(self):
        original = pair_fixture()
        changed = deepcopy(original)
        changed["content"]["missions"][0]["units"][0]["object_id"] = "missing-door"
        changed["content"]["missions"][0]["next_missions"] = ["missing-map"]
        changed["project"]["story"]["entry_scenes"]["intro"] = "missing-scene"
        first = reference_audit(changed)
        second = reference_audit(changed)
        self.assertEqual(first, second)
        self.assertFalse(first.passed)
        self.assertEqual(len(first.problems), 3)
        self.assertEqual({p.family for p in first.problems},
                         {"maps", "objects", "scenes"})
        self.assertTrue(all("Référence introuvable" in p.summary
                            for p in first.problems))
        actors = [r for r in resources(changed) if r.family == "actors"
                  and r.mission_id == "village"]
        only_actor = problems_for_selection(first, actors)
        self.assertEqual(len(only_actor), 1)
        self.assertEqual(only_actor[0].target_id, "missing-door")
        self.assertIn("Content.missions[village].units[guard]",
                      only_actor[0].path)
        self.assertEqual(original["content"]["missions"][0]["units"][0]
                         ["object_id"], "door")  # input not mutated

    def test_mission_scope_avoids_cross_scene_id_collisions(self):
        content = pair_fixture()
        content["content"]["missions"][1]["triggers"].append(
            {"id": "reference", "name": "Reference", "actor_id": "guard"})
        self.assertTrue(reference_audit(content).passed)
        content["content"]["missions"][1]["triggers"][0]["object_id"] = "door"
        audit = reference_audit(content)
        self.assertEqual(len(audit.problems), 1)
        self.assertEqual(audit.problems[0].source.mission_id, "forest")
        self.assertEqual(audit.problems[0].family, "objects")

    def test_advisory_audit_ignores_untyped_story_text(self):
        data = pair_fixture()
        data["project"]["story"]["scenes"][0]["text"] = (
            "The door, missing-door, is a story symbol.")
        self.assertTrue(reference_audit(data).passed)

    def test_limits_never_masquerade_as_clean_results(self):
        data = pair_fixture()
        partial = reference_audit(data, max_nodes=1)
        self.assertTrue(partial.truncated)
        self.assertFalse(partial.passed)
        self.assertGreater(partial.scanned_nodes, 0)
        data["content"]["missions"][0]["next_missions"] = [
            "missing-a", "missing-b", "missing-c"]
        capped = reference_audit(data, max_problems=1)
        self.assertTrue(capped.truncated)
        self.assertFalse(capped.passed)
        self.assertEqual(len(capped.problems), 1)

    def test_input_budgets_are_explicit(self):
        data = pair_fixture()
        for args in ({"max_nodes": 0}, {"max_nodes": True},
                     {"max_nodes": 1000001}, {"max_problems": 0},
                     {"max_problems": 10001}, {"max_problems": False}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                reference_audit(data, **args)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 unavailable")
class R49InspectorQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self, folder):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.sdk.reference import reference_project
        settings = QSettings(str(Path(folder) / "r49b2.ini"), QSettings.IniFormat)
        window = StudioWindow(AuthoringSession.new(*reference_project()),
                              settings=settings)
        return window

    def test_pending_edit_prevents_navigation_and_document_switch(self):
        with TemporaryDirectory() as folder:
            window = self.make_window(folder)
            from drawtemp.studio.workspace_model import resources
            actor = next(r for r in resources(window.session.snapshot())
                         if r.family == "actors")
            self.assertTrue(window.focus_resource(actor.key))
            field = window.property_widgets["name"][0]
            original = field.text()
            field.setText("Incomplete edit")
            field.textEdited.emit("Incomplete edit")
            self.assertFalse(window.resource_view.isEnabled())
            self.assertFalse(window.navigate("publication"))
            self.assertEqual(window._active_workspace, "project")
            self.assertFalse(window._confirm_leave())
            self.assertEqual(field.text(), "Incomplete edit")
            self.assertEqual(window.session.revision, 0)
            window.refresh()
            self.assertEqual(field.text(), "Incomplete edit")
            window.discard_inspector_changes()
            self.assertTrue(window.resource_view.isEnabled())
            self.assertEqual(window.property_widgets["name"][0].text(), original)
            self.assertTrue(window.navigate("publication"))
            with patch.object(window, "_confirm_leave", return_value=True):
                window.close()
            window.deleteLater()

    def test_broken_links_appear_inline_and_can_jump_to_source(self):
        from drawtemp.studio.qt_shell import StudioWindow
        from drawtemp.studio.workspace_model import resources
        with TemporaryDirectory() as folder:
            window = self.make_window(folder)
            actor = next(r for r in resources(window.session.snapshot())
                         if r.family == "actors")
            warning = ReferenceProblem(actor, "objects", "lost-door", "object_id",
                                       "Content.missions[village].units[guard].object_id")
            audit = ReferenceAudit((warning,), False, 8)
            with patch("drawtemp.studio.qt_shell.reference_audit", return_value=audit):
                window._r49_reference_key = None
                self.assertTrue(window.focus_resource(actor.key))
                self.assertIn("1 référence", window.reference_issues_label.text())
                matches = [window.links.item(i) for i in range(window.links.count())
                           if "lost-door" in window.links.item(i).text()]
                self.assertEqual(len(matches), 1)
                self.assertEqual(tuple(matches[0].data(0x0100)), actor.key)
                self.assertIn("object_id", matches[0].toolTip())
                window._r49_reference_key = None
                with patch("drawtemp.studio.qt_shell.QDialog.exec", return_value=0):
                    reported = window.inspect_references()
                self.assertEqual(reported, audit)
            with patch.object(window, "_confirm_leave", return_value=True):
                window.close()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
