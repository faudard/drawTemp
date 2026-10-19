"""R41.B1 Qt offscreen smoke: real Party Studio widgets and R1 transaction."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HAS_QT = importlib.util.find_spec("PySide6") is not None

from drawtemp.sdk.authoring import AuthoringSession
from tests_standalone.test_r41_classic_party import party_fixture
from drawtemp.studio.party_authoring import party_heroes

if _HAS_QT:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.party_qt import PartyStudioDialog


@unittest.skipUnless(_HAS_QT, "PySide6 optional")
class R41PartyStudioQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_preview_apply_undo_and_form_refresh(self):
        editor = AuthoringSession.new(*party_fixture())
        dialog = PartyStudioDialog(editor)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.objectName(), "r41-party-studio")
        self.assertEqual(dialog.members.rowCount(), len(party_heroes(editor.snapshot())))
        self.assertFalse(dialog.apply_button.isEnabled())
        dialog.capacity.setValue(3)
        self.assertFalse(dialog.apply_button.isEnabled())
        planned = dialog.preview()
        self.assertIsNotNone(planned, dialog.report.toPlainText())
        self.assertTrue(dialog.apply_button.isEnabled())
        self.assertEqual(editor.revision, 0)
        dialog.apply()
        self.assertEqual(editor.revision, 1)
        self.assertFalse(dialog.apply_button.isEnabled())
        project = editor.snapshot().to_dict()["project"]
        self.assertEqual(project["extensions"]["drawtemp.partyrpg"][
            "data"]["campaigns"]["main"]["max_active"], 3)
        editor.undo()
        self.assertEqual(editor.snapshot().to_dict()["project"][
            "extensions"]["drawtemp.partyrpg"]["data"]["campaigns"]["main"][
                "max_active"], 2)
        dialog.refresh()
        self.assertEqual(dialog.capacity.value(), 2)


if __name__ == "__main__":
    unittest.main()
