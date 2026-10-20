"""R63.B Qt offscreen regression: typed Studio forms, map placement and history."""
from __future__ import annotations

from copy import deepcopy
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.survival_designer_qt import (
        SurvivalDesignerDialog, starter_survival, parse_materials)
    QT = True
except ImportError:
    QT = False

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.survival_authoring import preview_survival_design
from sporebound.survival import EXTENSION
from tests_standalone.test_r25_scene_router import scene_fixture


@unittest.skipUnless(QT, "PySide6 is unavailable")
class R63SurvivalQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self):
        content, project = scene_fixture()
        session = AuthoringSession(content, project)
        return SurvivalDesignerDialog(session), session

    def test_starter_valid_and_map_click_places_scene_checked_resources(self):
        dialog, session = self._dialog()
        self.assertEqual(len(dialog.document["recipes"]), 2)
        self.assertEqual(dialog.lists["nodes"].count(), 3)
        self.assertGreater(len(dialog.map_scene.items()), 0)
        dialog.tabs.setCurrentIndex(2)  # nodes
        dialog.lists["nodes"].setCurrentRow(0)
        before = deepcopy(session.snapshot().to_dict()["project"])
        self.assertFalse(dialog.place_selected(2, 1))  # blocked by R25 map
        self.assertEqual(dialog.document["nodes"][0].get("pos"), None)
        self.assertTrue(dialog.place_selected(0, 0))
        self.assertEqual(dialog.document["nodes"][0]["pos"], [0, 0])
        self.assertEqual(session.snapshot().to_dict()["project"], before)
        self.assertTrue(dialog.undo_draft())
        self.assertNotIn("pos", dialog.document["nodes"][0])
        self.assertTrue(dialog.redo_draft())
        self.assertTrue(dialog.preview())
        self.assertIn("Recettes : 2", dialog.report.toPlainText())
        self.assertTrue(dialog.apply())
        self.assertIn(EXTENSION,
                      session.snapshot().to_dict()["project"]["extensions"])
        session.undo()
        self.assertNotIn(EXTENSION,
                         session.snapshot().to_dict()["project"].get("extensions", {}))
        session.redo()
        self.assertIn(EXTENSION,
                      session.snapshot().to_dict()["project"]["extensions"])
        dialog.close()

    def test_recipe_edit_and_needs_are_both_local_until_apply(self):
        dialog, session = self._dialog()
        revision = session.revision
        old_recipe = deepcopy(dialog.document["recipes"][0])
        row = {**old_recipe, "energy_cost": 7,
               "inputs": "wood:2, stone:1",
               "outputs": "camp:1"}
        self.assertTrue(dialog.commit_row("recipes", row, 0))
        self.assertEqual(dialog.document["recipes"][0]["inputs"]["wood"], 2)
        dialog.need_fields["temperature"].setValue(60)
        self.assertTrue(dialog.commit_needs())
        self.assertEqual(dialog.document["needs"]["temperature"], 60)
        self.assertEqual(session.revision, revision)
        self.assertTrue(dialog.undo_draft())
        self.assertEqual(dialog.document["needs"]["temperature"], 80)
        self.assertTrue(dialog.undo_draft())
        self.assertEqual(dialog.document["recipes"][0], old_recipe)
        self.assertTrue(dialog.redo_draft())
        self.assertTrue(dialog.redo_draft())
        self.assertTrue(dialog.apply())
        self.assertEqual(session.revision, revision + 1)
        document = session.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"]
        self.assertEqual(document["needs"]["temperature"], 60)
        self.assertEqual(document["recipes"][0]["inputs"]["wood"], 2)
        dialog.close()

    def test_stale_preview_rejected_without_overwriting_project(self):
        first, session = self._dialog()
        second = SurvivalDesignerDialog(session)
        self.assertTrue(first.apply())
        previous = deepcopy(session.snapshot().to_dict()["project"])
        with self.assertRaises(ValueError):
            preview_survival_design(
                session, second.document,
                expected_revision=second.source_revision)
        self.assertEqual(session.snapshot().to_dict()["project"], previous)
        first.close()
        second.close()

    def test_material_parser_rejects_injection_duplicates_and_bounds(self):
        self.assertEqual(parse_materials("wood:2, stone:1", {"wood", "stone"}),
                         {"wood": 2, "stone": 1})
        for raw in ("wood:0", "wood:-1", "wood:True", "wood:100",
                    "wood:1,wood:2", "stone:1;import os", "",
                    "unknown:1", "wood:1,"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_materials(raw, {"wood", "stone"})

    def test_qt_studio_shell_exposes_designer_command(self):
        from drawtemp.studio.qt_shell import StudioWindow
        content, project = scene_fixture()
        studio = StudioWindow(AuthoringSession(content, project))
        self.assertIn("r63_survival", studio.commands)
        self.assertTrue(studio.commands["r63_survival"].isEnabled())
        studio.close()


if __name__ == "__main__":
    unittest.main()
