"""R53.B1 Qt offscreen smoke: native combo editor and R1 Undo/Redo."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HAS_QT = importlib.util.find_spec("PySide6") is not None

from drawtemp.sdk.authoring import AuthoringSession
from tests_standalone.test_r53_party_composer import composer_fixture
from drawtemp.studio.party_orchestration_authoring import inspect_orchestration

if _HAS_QT:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.party_orchestration_qt import R53PartyComposerDialog


@unittest.skipUnless(_HAS_QT, "PySide6 optional")
class R53PartyComposerQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_visual_leader_slots_combo_skills_preview_apply_and_undo(self):
        editor = AuthoringSession.new(*composer_fixture())
        dialog = R53PartyComposerDialog(editor)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.objectName(), "r53-party-composer")
        self.assertEqual(dialog.leader.count(), 2)
        self.assertEqual(dialog.formation.rowCount(), 2)
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertEqual(dialog.combos.rowCount(), 0)

        dialog.leader.setCurrentIndex(dialog.leader.findData("etienne"))
        dialog.formation.cellWidget(0, 1).setCurrentIndex(
            dialog.formation.cellWidget(0, 1).findData("rear"))
        dialog.formation.cellWidget(1, 1).setCurrentIndex(
            dialog.formation.cellWidget(1, 1).findData("front"))
        dialog.add_combo()
        self.assertEqual(dialog.combos.rowCount(), 1)
        self.assertEqual(dialog.skills.rowCount(), 2)
        self.assertEqual(dialog.combos.item(0, 0).text(), "combo_1")
        self.assertEqual(dialog.skills.cellWidget(0, 1).itemData(1), "estoc")
        dialog.skills.cellWidget(0, 1).setCurrentIndex(
            dialog.skills.cellWidget(0, 1).findData("estoc"))
        dialog.skills.cellWidget(1, 1).setCurrentIndex(
            dialog.skills.cellWidget(1, 1).findData("garde_rapprochee"))

        preview = dialog.preview()
        self.assertIsNotNone(preview, dialog.report.toPlainText())
        self.assertIn("native_impact", dialog.report.toPlainText())
        self.assertEqual(editor.revision, 0)
        self.assertTrue(dialog.apply_button.isEnabled())

        # Any edit after a valid preview invalidates Apply.
        dialog.leader.setCurrentIndex(dialog.leader.findData("jeanne"))
        self.assertFalse(dialog.apply_button.isEnabled())
        dialog.leader.setCurrentIndex(dialog.leader.findData("etienne"))
        self.assertIsNotNone(dialog.preview(), dialog.report.toPlainText())
        dialog.apply()
        self.assertEqual(editor.revision, 1)
        result = inspect_orchestration(editor.snapshot(), "main")
        self.assertTrue(result["enabled"])
        self.assertEqual(result["leader"], "etienne")
        self.assertEqual(result["formation"], ["rear", "front"])
        self.assertEqual(result["combos"][0]["skills"], {
            "jeanne": "estoc", "etienne": "garde_rapprochee"})

        editor.undo()
        dialog.refresh()
        self.assertFalse(inspect_orchestration(
            editor.snapshot(), "main")["enabled"])
        editor.redo()
        dialog.refresh()
        self.assertEqual(dialog.combos.rowCount(), 1)
        self.assertEqual(dialog.skills.rowCount(), 2)

    def test_keyboard_buttons_launch_preview_and_combo_creation(self):
        editor = AuthoringSession.new(*composer_fixture())
        dialog = R53PartyComposerDialog(editor)
        self.addCleanup(dialog.close)
        dialog.show()
        dialog.add_button.setFocus()
        QTest.keyClick(dialog.add_button, Qt.Key_Space)
        self.assertEqual(dialog.combos.rowCount(), 1)
        dialog.preview_button.setFocus()
        QTest.keyClick(dialog.preview_button, Qt.Key_Space)
        self.assertTrue(dialog.apply_button.isEnabled(),
                        dialog.report.toPlainText())
        self.assertEqual(editor.revision, 0)

    def test_duplicate_slot_and_unavailable_combo_are_rejected(self):
        editor = AuthoringSession.new(*composer_fixture())
        dialog = R53PartyComposerDialog(editor)
        self.addCleanup(dialog.close)
        dialog.formation.cellWidget(1, 1).setCurrentIndex(
            dialog.formation.cellWidget(1, 1).findData("front"))
        self.assertIsNone(dialog.preview())
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertEqual(editor.revision, 0)
        dialog.refresh()
        dialog.add_combo()
        dialog.combos.item(0, 1).setText("jeanne, missing")
        self.assertIsNone(dialog.preview())
        self.assertEqual(editor.revision, 0)


if __name__ == "__main__":
    unittest.main()
