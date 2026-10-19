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
