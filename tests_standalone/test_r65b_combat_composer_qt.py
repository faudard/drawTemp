"""Optional offscreen Qt smoke: editable R65.B Composer and R1 history."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HAS_QT = importlib.util.find_spec("PySide6") is not None

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from sporebound.action_combat_catalog_r65 import catalog_from_project

if _HAS_QT:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.combat_composer_r65_qt import CombatComposerDialog


@unittest.skipUnless(_HAS_QT, "PySide6 optional")
class CombatComposerQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_preview_edit_apply_undo_redo(self):
        session = AuthoringSession.new(*reference_project())
        before = session.snapshot().to_dict()
        dialog = CombatComposerDialog(session)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.objectName(), "r65-combat-composer")
        self.assertEqual(dialog.moves.rowCount(), 1)
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertEqual(dialog.hitbox.item(4, 4).text(), "H")
        self.assertEqual(dialog.hitbox.item(4, 5).text(), "E")
        dialog.moves.item(0, 4).setText("5")
        dialog.add_move()
        self.assertEqual(dialog.moves.rowCount(), 2)
        dialog.add_pattern()
        self.assertEqual(dialog.patterns.rowCount(), 1)
        dialog.patterns.item(0, 1).setText("2")
        dialog.patterns.item(0, 2).setText("50")
        dialog.preview()
        self.assertTrue(dialog.apply_button.isEnabled(), dialog.report.toPlainText())
        self.assertEqual(session.snapshot().to_dict(), before)
        dialog.apply()
        catalog = catalog_from_project(session.snapshot().to_dict()["project"])
        self.assertEqual(catalog["presets"][0]["rules"]["combo"][0]["damage"], 5)
        self.assertEqual(catalog["presets"][0]["boss_patterns"][0]["phase"], 2)
        dialog.undo()
        self.assertEqual(session.snapshot().to_dict()["project"], before["project"])
        dialog.redo()
        self.assertEqual(
            catalog_from_project(session.snapshot().to_dict()["project"]),
            catalog)

    def test_modified_forms_and_stale_preview_cannot_apply(self):
        session = AuthoringSession.new(*reference_project())
        dialog = CombatComposerDialog(session)
        self.addCleanup(dialog.close)
        dialog.preview()
        self.assertTrue(dialog.apply_button.isEnabled())
        dialog.label.setText("Autre nom")
        self.assertFalse(dialog.apply_button.isEnabled())
        session.apply(session.preview_project(
            lambda project: {**project, "subtitle": "Autre version"}))
        dialog.preview()
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertIn("refusée", dialog.report.toPlainText())
        dialog.apply()
        self.assertEqual(
            catalog_from_project(session.snapshot().to_dict()["project"])["presets"],
            [])

    def test_invalid_telegraph_is_reported_no_project_write(self):
        session = AuthoringSession.new(*reference_project())
        dialog = CombatComposerDialog(session)
        self.addCleanup(dialog.close)
        before = session.snapshot().to_dict()
        dialog.cues.item(0, 2).setText("100")
        dialog.preview()
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertIn("refusée", dialog.report.toPlainText())
        self.assertEqual(before, session.snapshot().to_dict())


if __name__ == "__main__":
    unittest.main()
