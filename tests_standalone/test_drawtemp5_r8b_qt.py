"""R8.B Qt offscreen UI test: real talent graph and encounter scene."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "PySide6 optional extra unavailable")
class R8AdvancedQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.sdk.reference import reference_project
        content, project = reference_project()
        self.session = AuthoringSession.new(content, project)

    def test_talent_dialog_updates_graph_from_real_transactions(self):
        from drawtemp.studio.rpg_database import lancer_example
        from drawtemp.studio.r8_workbenches_qt import TalentDialog

        lancer_example(self.session)
        dialog = TalentDialog(self.session, selected_job="r8_lancier")
        try:
            self.assertEqual(dialog.job.currentText(), "r8_lancier")
            dialog.talent.setEditText("spear_wall")
            dialog.jp.setValue(2)
            dialog.bonuses.setText("defense=2")
            dialog._create()
            self.assertIn("spear_wall", dialog.workbench.talents("r8_lancier"))
            self.assertGreater(len(dialog.talent_graph.scene().items()), 0)
            self.assertTrue(self.session.snapshot().dirty)
        finally:
            dialog.close()

    def test_encounter_dialog_shows_placed_units_and_reloads(self):
        from drawtemp.sdk.reference import MISSION
        from drawtemp.studio.rpg_database import lancer_example
        from drawtemp.studio.r8_workbenches_qt import EncounterDialog

        lancer_example(self.session)
        dialog = EncounterDialog(self.session, mission_id=MISSION)
        try:
            before = dialog.table.rowCount()
            self.assertGreaterEqual(before, 2)
            self.assertEqual(dialog._mission(), MISSION)
            self.assertGreater(len(dialog.scene.items()), before)
            dialog._picked(2, 3)
            self.assertEqual((dialog.x.value(), dialog.y.value()), (2, 3))
            self.assertIn("aperçu de placement", dialog.status.text())
            self.assertFalse(dialog.workbench.session.snapshot().dirty is False)
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
