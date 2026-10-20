"""R74.B Qt offscreen: opt-in, local variant diff, single R1 edit and safety."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

try:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication, QMessageBox
    from drawtemp.studio.r74_assist_qt import R74DungeonAssistDialog
except ImportError:
    QApplication = None

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.roguelite_authoring import preview_roguelite_project
from drawtemp.sdk.procgen_prefabs import demo_library
from sporebound.roguelite import EXTENSION


@unittest.skipIf(QApplication is None, "PySide6 optional")
class AssistedDungeonQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["r74b-test"])

    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.document = self.root / "project.json"
        AuthoringSession.new(*reference_project()).save_as(self.document)
        self.session = AuthoringSession.open(self.document)
        self.dialog = R74DungeonAssistDialog(self.session)
        self.addCleanup(self.dialog.close)
        self.before = self.session.snapshot().to_dict()
        self.bytes_before = self.document.read_bytes()

    def test_preview_and_graph_compare_never_write(self):
        suggestions = self.dialog.preview_generation()
        self.assertEqual(len(suggestions), 3)
        self.assertEqual(self.dialog.variant_table.rowCount(), 3)
        self.assertTrue(self.dialog.apply_button.isEnabled())
        self.assertGreater(len(self.dialog.candidate_graph.scene().items()), 0)
        self.assertIn("topology_changed", self.dialog.diff_report.toPlainText())
        self.dialog.variant_table.selectRow(1)
        self.assertIn("candidate_seed", self.dialog.diff_report.toPlainText())
        self.assertEqual(self.session.snapshot().to_dict(), self.before)
        self.assertEqual(self.document.read_bytes(), self.bytes_before)

    def test_pin_and_local_recipe_edit_show_semantic_diff(self):
        self.assertTrue(self.dialog.preview_generation())
        self.dialog.variant_table.selectRow(1)
        pinned = self.dialog.pin_selected()
        self.assertEqual(pinned.recipe["rooms"], 8)
        self.dialog.rooms_spin.setValue(9)
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.dialog.variant_table.rowCount(), 0)
        revised = self.dialog.preview_generation()
        self.assertEqual(len(revised), 3)
        self.assertEqual(revised[0].recipe["rooms"], 9)
        text = self.dialog.diff_report.toPlainText()
        self.assertIn('"rooms_before": 8', text)
        self.assertIn('"rooms_after": 9', text)
        self.assertTrue(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_default_confirmation_is_no_and_cancel_has_no_effect(self):
        self.dialog.preview_generation()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No) as prompt:
            self.assertIsNone(self.dialog.apply_selected())
            self.assertEqual(prompt.call_args.args[-1], QMessageBox.No)
        self.assertEqual(self.session.snapshot().to_dict(), self.before)
        self.assertEqual(self.document.read_bytes(), self.bytes_before)

    def test_approval_changes_only_project_and_undo_redo_no_disk(self):
        suggestions = self.dialog.preview_generation()
        self.dialog.variant_table.selectRow(1)
        chosen = suggestions[1]
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            applied = self.dialog.apply_selected()
        self.assertIsNotNone(applied)
        after = applied.snapshot.to_dict()
        self.assertEqual(after["content"], self.before["content"])
        self.assertEqual(after["project"]["extensions"][EXTENSION]["data"]
                         ["recipe"]["seed"], chosen.seed)
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertTrue(self.dialog.undo_button.isEnabled())
        self.assertEqual(self.document.read_bytes(), self.bytes_before)
        undone = self.dialog.undo_application()
        self.assertEqual(undone.snapshot.to_dict()["project"], self.before["project"])
        self.assertTrue(self.dialog.redo_button.isEnabled())
        redone = self.dialog.redo_application()
        self.assertEqual(redone.snapshot.to_dict()["project"], after["project"])
        self.assertEqual(self.document.read_bytes(), self.bytes_before)

    def test_reject_and_parameter_change_invalidate_current_lease(self):
        self.assertTrue(self.dialog.preview_generation())
        self.dialog.reject_proposals()
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.dialog.variant_table.rowCount(), 0)
        self.assertIsNone(self.dialog.apply_selected())
        self.assertEqual(self.dialog.preview_generation().__len__(), 3)
        self.dialog.seed_spin.setValue(75)
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_stale_external_revision_is_rejected_and_does_not_apply_twice(self):
        selected = self.dialog.preview_generation()[0]
        plan = preview_roguelite_project(
            self.session, selected.recipe, demo_library(), biome="ruins"
        )
        self.session.apply(plan)
        revision = self.session.revision
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.assertIsNone(self.dialog.apply_selected())
        self.assertEqual(self.session.revision, revision)
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertIn("bloquée", self.dialog.status.text())

    def test_invalid_constraints_and_rights_are_fail_closed(self):
        self.dialog.branches_spin.setValue(0)
        self.assertEqual(self.dialog.preview_generation(), ())
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertIn("refusée", self.dialog.status.text())
        self.assertEqual(self.session.snapshot().to_dict(), self.before)
        library = demo_library()
        library["prefabs"][0]["mission_id"] = MISSION
        denied = R74DungeonAssistDialog(self.session, library=library)
        self.addCleanup(denied.close)
        self.assertEqual(denied.preview_generation(), ())
        self.assertIn("rights", denied.status.text().lower())
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_studio_command_palette_and_tools_action(self):
        from drawtemp.studio.qt_shell import StudioWindow
        settings = QSettings(str(self.root / "settings.ini"), QSettings.IniFormat)
        studio = StudioWindow(self.session, settings=settings)
        self.addCleanup(studio.close)
        self.assertIn("r74_dungeons", studio.commands)
        action = studio.commands["r74_dungeons"]
        self.assertTrue(action.isEnabled())
        self.assertIn("R74", action.text())
        tool_actions = [a for menu in studio.menuBar().actions()
                        if menu.menu() for a in menu.menu().actions()]
        self.assertIn(action, tool_actions)
        with patch.object(R74DungeonAssistDialog, "exec", return_value=0) as exec_dialog:
            studio.open_r74_dungeons()
            exec_dialog.assert_called_once()


if __name__ == "__main__":
    unittest.main()
