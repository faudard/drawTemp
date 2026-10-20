"""R37.E offscreen Qt Boss Director smoke: real trigger editing, single R1 Undo."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from drawtemp.sdk.authoring import AuthoringSession
from tests_standalone.test_r37_boss_director import fixture

_HAS_QT = importlib.util.find_spec("PySide6") is not None
if _HAS_QT:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.ai_boss_qt import BossDirectorDialog


@unittest.skipUnless(_HAS_QT, "PySide6 optional")
class BossDirectorQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_create_phase_edit_preview_and_undo_redo(self):
        content, project, _ = fixture(with_director=False)
        session = AuthoringSession.new(content, project)
        dialog = BossDirectorDialog(session)
        self.assertEqual(dialog.objectName(), "r37-boss-dialog")
        self.assertEqual(dialog.candidate.count(), 1)
        self.assertEqual(dialog.director.count(), 0)
        dialog.add()
        self.assertEqual(session.revision, 0)
        self.assertTrue(dialog.buttons["apply"].isEnabled())
        dialog.apply()
        self.assertEqual(session.revision, 1)
        self.assertEqual(dialog.director.count(), 1)
        self.assertEqual(dialog.phase.count(), 2)
        dialog.phase.setCurrentIndex(1)
        dialog.label.setText("Storm Phase")
        dialog.cue.setText("The boss is drawing strength")
        dialog.validate()
        self.assertTrue(dialog.buttons["apply"].isEnabled())
        dialog.apply()
        self.assertEqual(session.revision, 2)
        self.assertEqual(
            dialog.designer.catalog()[0]["phases"][1]["label"],
            "Storm Phase")
        dialog.inspect()
        self.assertIn('"preview_only": true',
                      dialog.diagnostics.toPlainText())
        self.assertIn("authored_mission_triggers",
                      dialog.diagnostics.toPlainText())
        dialog.undo()
        self.assertEqual(dialog.designer.catalog()[0]["phases"][1]["label"],
                         "Phase 3")
        dialog.redo()
        self.assertEqual(dialog.designer.catalog()[0]["phases"][1]["label"],
                         "Storm Phase")
        dialog.close()


if __name__ == "__main__":
    unittest.main()
