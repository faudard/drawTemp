"""R62.B.1 QTest-compatible offscreen native Farm Studio smoke."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QDialog
    from drawtemp.studio.farming_qt import FarmRecordEditor, FarmStudioDialog
except ImportError:
    QApplication = None
    QDialog = None

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.farming_life import EXTENSION
from tests_standalone.test_r25_scene_router import scene_fixture


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class FarmStudioQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        content, project = scene_fixture()
        self.session = AuthoringSession(content, project)
        self.dialog = FarmStudioDialog(self.session)
        self.content = content

    def tearDown(self):
        self.dialog.close()

    def test_native_typed_form_preview_apply_and_global_history(self):
        draft = self.dialog.draft
        self.assertFalse(draft.clock_present)
        self.dialog.initialize_clock.setChecked(True)
        editor = FarmRecordEditor("plots", draft, parent=self.dialog)
        editor.ident.setText("field")
        editor.scene.setCurrentText("arrival")
        editor.soil.setCurrentText("loam")
        editor._accept_record()
        self.assertEqual(editor.result(), QDialog.Accepted)
        self.assertEqual(editor.record, {
            "id": "field", "scene": "arrival", "soil": "loam"})
        draft.upsert("plots", editor.record)
        self.dialog._refresh()
        self.assertEqual(self.dialog.lists["plots"].count(), 1)
        self.assertTrue(self.dialog.undo_button.isEnabled())
        self.dialog._undo()
        self.assertEqual(self.dialog.lists["plots"].count(), 0)
        self.dialog._redo()
        self.assertEqual(self.dialog.lists["plots"].count(), 1)
        self.assertIsNotNone(self.dialog._preview())
        self.assertNotIn(EXTENSION, self.session.snapshot().to_dict()
                         ["project"].get("extensions", {}))
        self.dialog._apply()
        self.assertEqual(self.dialog.result(), QDialog.Accepted)
        self.assertEqual(self.session.revision, 1)
        self.assertIn(EXTENSION, self.session.snapshot().to_dict()
                      ["project"]["extensions"])
        self.session.undo()
        self.assertNotIn(EXTENSION, self.session.snapshot().to_dict()
                         ["project"].get("extensions", {}))

    def test_crop_and_animal_forms_reject_empty_multiselection(self):
        draft = self.dialog.draft
        crop = FarmRecordEditor("crops", draft, parent=self.dialog)
        crop.ident.setText("turnip")
        for check in crop.season_checks:
            check.setChecked(False)
        crop._accept_record()
        self.assertEqual(crop.result(), QDialog.Accepted)
        before = draft.document
        from sporebound.model import RuleError
        with self.assertRaises(RuleError):
            draft.upsert("crops", crop.record)
        self.assertEqual(draft.document, before)
        animal = FarmRecordEditor("animals", draft, parent=self.dialog)
        animal.ident.setText("hen")
        animal._accept_record()
        self.assertEqual(animal.record["interval_days"], 1)
        self.assertTrue(draft.upsert("animals", animal.record))


if __name__ == "__main__":
    unittest.main()
