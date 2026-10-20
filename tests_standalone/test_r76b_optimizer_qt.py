"""Optional R76.B1 Qt-offscreen smoke: actual proposal, preview and approval."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from drawtemp.studio.r76_optimizer_qt import OptimizerDialog
except ImportError:
    QApplication = None

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from tests_standalone.test_r76_asset_audit import png
from tests_standalone.test_r76b_optimizer import make_registry


@unittest.skipIf(QApplication is None, "PySide6 unavailable")
class OptimizerStudioQtSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "source"
        self.root.mkdir()
        (self.root / "a.png").write_bytes(png())
        (self.root / "b.png").write_bytes(png())
        self.content_path = self.root / "demo.json"
        self.content_path.write_text("{}", encoding="utf-8")
        content, project = reference_project()
        project_data = project.to_dict()
        project_data["assets"] = make_registry().to_dict()
        self.session = AuthoringSession.new(content, project_data)

    def test_review_preview_explicit_approval_and_derived_undo(self):
        dialog = OptimizerDialog(self.session, self.content_path)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.objectName(), "r76-optimizer-studio")
        self.assertEqual(dialog.table.rowCount(), 1)
        self.assertIn("Octets et SHA identiques", dialog.comparison.text())
        self.assertFalse(dialog.apply_button.isEnabled())
        dest = self.root.parent / "derived"
        dialog.output.setText(str(dest))
        self.assertFalse(dialog.apply_button.isEnabled())
        dialog.approve.setChecked(True)
        self.assertTrue(dialog.apply_button.isEnabled())
        revision = self.session.revision
        self.assertTrue(dialog.apply())
        self.assertTrue(dest.is_dir())
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertTrue(dialog.undo_button.isEnabled())
        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(dialog.undo_derived())
        self.assertFalse(dest.exists())
        self.assertEqual(self.session.revision, revision)
        self.assertTrue((self.root / "a.png").is_file())
        self.assertTrue((self.root / "b.png").is_file())

    def test_dirty_revision_refuses_stale_preview(self):
        dialog = OptimizerDialog(self.session, self.content_path)
        self.addCleanup(dialog.close)
        self.session._revision += 1
        self.assertFalse(dialog.refresh())
        self.assertIsNone(dialog.plan)


if __name__ == "__main__":
    unittest.main()
