"""R75.B Qt preview/consent smoke without an external service."""
import importlib.util
import os
import unittest
from unittest.mock import patch

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "Optional PySide6 not installed")
class R75NarrativeDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from drawtemp.studio.r75_narrative_assist_qt import R75NarrativeAssistDialog
        self.session = AuthoringSession.new(*reference_project())
        self.dialog = R75NarrativeAssistDialog(self.session)
        self.before = self.session.snapshot().to_dict()

    def tearDown(self):
        self.dialog.close()

    def test_preview_diff_has_sources_paths_and_requires_approval(self):
        self.assertFalse(self.dialog.apply_button.isEnabled())
        review = self.dialog.preview_proposal()
        self.assertIsNotNone(review)
        self.assertTrue(self.dialog.apply_button.isEnabled())
        output = self.dialog.preview_text.toPlainText()
        self.assertIn("SHA-256", output)
        self.assertIn("Attribution", output)
        self.assertIn("CHEMINS TÉMOINS", output)
        self.assertIn("r75_rescue", output)
        self.assertEqual(self.session.snapshot().to_dict(), self.before)
        self.assertIsNone(self.dialog.apply_review(approved=False))
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_cancelled_confirmation_no_mutation_approved_one_undo(self):
        from PySide6.QtWidgets import QMessageBox
        self.dialog.preview_proposal()
        with patch("drawtemp.studio.r75_narrative_assist_qt.QMessageBox") as popup:
            popup.Yes = QMessageBox.Yes
            popup.No = QMessageBox.No
            popup.question.return_value = QMessageBox.No
            self.assertIsNone(self.dialog.confirm_apply())
        self.assertEqual(self.before, self.session.snapshot().to_dict())
        changed = self.dialog.apply_review(approved=True)
        self.assertIsNotNone(changed)
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.session.undo().snapshot.to_dict()["project"],
                         self.before["project"])

    def test_parameter_change_invalidates_and_stale_revision_is_denied(self):
        self.dialog.preview_proposal()
        self.dialog.prefix.setText("r75other")
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertIsNone(self.dialog.apply_review(approved=True))
        self.dialog.preview_proposal()
        self.session.apply(self.session.preview_project(
            lambda project: {**project, "subtitle": "external"}))
        self.assertIsNone(self.dialog.apply_review(approved=True))
        self.assertIn("refusée", self.dialog.status.text())


if __name__ == "__main__":
    unittest.main()
