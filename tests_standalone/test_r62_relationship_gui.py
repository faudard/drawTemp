"""R62.B.2: offscreen Qt Relationship Studio smoke and history contract."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QDialog
    from drawtemp.studio.relationship_qt import RelationshipStudioDialog
except ImportError:
    QApplication = None
    QDialog = None

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.relationship_life import EXTENSION
from tests_standalone.test_r35_living_world import fixture as world_fixture


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class RelationshipStudioQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        content, project = world_fixture()
        self.session = AuthoringSession(content, project)
        self.dialog = RelationshipStudioDialog(self.session)

    def tearDown(self):
        self.dialog.close()

    def test_editor_typed_npc_gift_preview_apply_and_global_undo(self):
        dialog = self.dialog
        dialog.npc.setCurrentText("merchant")
        dialog.activity.setCurrentText("trade")
        dialog.talk_gain.setValue(4)
        dialog.gift_item.setCurrentIndex(0)
        dialog.gift_gain.setValue(7)
        dialog._upsert_gift()
        self.assertEqual(dialog.gifts.count(), 1)
        dialog._save_person()
        self.assertEqual(dialog.people.count(), 1)
        self.assertTrue(dialog.undo_btn.isEnabled())
        dialog._undo()
        self.assertEqual(dialog.people.count(), 0)
        dialog._redo()
        self.assertEqual(dialog.people.count(), 1)
        self.assertEqual(dialog._preview()["npc_count"], 1)
        self.assertNotIn(EXTENSION,
                         self.session.snapshot().to_dict()["project"]
                         ["extensions"])
        dialog._apply()
        self.assertEqual(dialog.result(), QDialog.Accepted)
        self.assertEqual(self.session.revision, 1)
        stored = self.session.snapshot().to_dict()["project"]["extensions"]
        self.assertEqual(stored[EXTENSION]["data"]["relationships"][0]
                         ["gifts"][0]["gain"], 7)
        self.session.undo()
        self.assertNotIn(EXTENSION, self.session.snapshot().to_dict()
                         ["project"]["extensions"])

    def test_rejected_duplicate_does_not_mutate_draft(self):
        dialog = self.dialog
        dialog.npc.setCurrentText("merchant")
        dialog._save_person()
        initial = dialog.draft.document
        dialog._new()
        with patch("drawtemp.studio.relationship_qt.QMessageBox.warning") as warn:
            dialog._save_person()
        warn.assert_called_once()
        self.assertEqual(dialog.draft.document, initial)


if __name__ == "__main__":
    unittest.main()
