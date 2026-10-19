"""R34.B Qt offscreen smoke. Not GPU/onscreen certification."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.procgen_qt import ProcGenPreviewDialog
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "PySide6 unavailable")
class ProceduralPreviewQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_explicit_project_apply_is_undoable(self):
        from unittest.mock import patch
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.sdk.reference import reference_project
        from sporebound.roguelite import EXTENSION
        from PySide6.QtWidgets import QMessageBox

        content, project = reference_project()
        session = AuthoringSession.new(content, project)
        dialog = ProcGenPreviewDialog(content=content, project=project,
                                       session=session)
        self.assertTrue(dialog.apply_project_button.isEnabled())
        self.assertNotIn(EXTENSION, session.snapshot().project.get("extensions", {}))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            transition = dialog.apply_to_project()
        self.assertIsNotNone(transition)
        self.assertEqual(session.snapshot().project["extensions"][EXTENSION]
                         ["data"]["recipe"]["seed"], 42)
        session.undo()
        self.assertNotIn(EXTENSION, session.snapshot().project.get("extensions", {}))
        dialog.close()

    def test_seed_preview_batch_and_invalid_no_stale_export(self):
        dialog = ProcGenPreviewDialog()
        self.assertEqual(dialog.objectName(), "r34-procgen-dialog")
        first = dialog.preview()
        self.assertIsNotNone(first)
        self.assertIn("digest", dialog.report.toPlainText())
        self.assertGreater(dialog.graph.scene().itemsBoundingRect().width(), 0)
        report = dialog.batch()
        self.assertEqual(len(report), 25)
        self.assertTrue(all(row["passed"] for row in report))
        dialog.branches.setValue(0)
        self.assertIsNone(dialog.preview())
        self.assertIsNone(dialog._last_layout)
        self.assertIn("refusée", dialog.report.toPlainText())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
