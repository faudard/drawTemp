"""R41.B2 Qt Encounter Studio test (offscreen only; not hardware UX proof)."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HAS_QT = importlib.util.find_spec("PySide6") is not None

from drawtemp.sdk.authoring import AuthoringSession
from tests_standalone.test_r41_encounter import encounter_fixture

if _HAS_QT:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.encounter_qt import EncounterStudioDialog


@unittest.skipUnless(_HAS_QT, "PySide6 optional")
class EncounterQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_encounter_selection_preview_apply_undo(self):
        editor = AuthoringSession.new(*encounter_fixture())
        dialog = EncounterStudioDialog(editor)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.objectName(), "r41-encounter-studio")
        self.assertIn("inn", [dialog.scene.itemData(i)
                              for i in range(dialog.scene.count())])
        self.assertFalse(dialog.apply_button.isEnabled())
        index = dialog.existing.findData("sparring")
        self.assertGreaterEqual(index, 0)
        dialog.existing.setCurrentIndex(index)
        self.assertEqual(dialog.encounter_id.text(), "sparring")
        self.assertEqual(dialog.gold.value(), 17)
        dialog.gold.setValue(23)
        self.assertFalse(dialog.apply_button.isEnabled())
        draft = dialog.preview()
        self.assertIsNotNone(draft, dialog.preview_text.toPlainText())
        self.assertEqual(editor.revision, 0)
        dialog.apply()
        self.assertEqual(editor.revision, 1)
        self.assertEqual(editor.snapshot().to_dict()["project"][
            "extensions"]["drawtemp.partyrpg"]["data"]["encounters"][
                "sparring"]["reward_gold"], 23)
        editor.undo()
        self.assertEqual(editor.snapshot().to_dict()["project"][
            "extensions"]["drawtemp.partyrpg"]["data"]["encounters"][
                "sparring"]["reward_gold"], 17)


if __name__ == "__main__":
    unittest.main()
