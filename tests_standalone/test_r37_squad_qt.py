"""R37.D3 optional Qt smoke: squad role authoring/atomic Undo/Redo."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.advanced_ai import EXTENSION
from tests_standalone.test_r37_squad import fixture

_HAS_QT = importlib.util.find_spec("PySide6") is not None
if _HAS_QT:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.ai_squad_qt import AISquadDialog


@unittest.skipUnless(_HAS_QT, "PySide6 Qt Studio dependency is optional")
class SquadQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_role_range_preview_apply_and_undo(self):
        content, project = fixture()
        session = AuthoringSession.new(content, project)
        window = AISquadDialog(session)
        self.assertEqual(window.objectName(), "r37-squad-dialog")
        self.assertEqual(window.actor.count(), 3)
        original = session.snapshot().to_dict()["project"]
        window.radio_range.setValue(4)
        window.role.setCurrentIndex(window.role.findData("protector"))
        window.preview()
        self.assertEqual(session.revision, 0)
        self.assertTrue(window.buttons["apply"].isEnabled())
        window.apply()
        self.assertEqual(session.revision, 1)
        edited = session.snapshot().to_dict()["project"]
        self.assertNotEqual(edited, original)
        bound = next(a for a in edited["extensions"][EXTENSION]["data"]["agents"]
                     if a["id"] == window.actor.currentData())
        self.assertEqual(bound["squad"]["role"], "protector")
        self.assertEqual(bound["squad"]["radio_range"], 4)
        window.undo()
        self.assertEqual(session.snapshot().to_dict()["project"], original)
        window.redo()
        self.assertEqual(session.snapshot().to_dict()["project"], edited)
        window.close()


if __name__ == "__main__":
    unittest.main()
