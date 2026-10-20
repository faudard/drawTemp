"""R56.B Qt offscreen smoke: explicit capture and read-only linked drilldown."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtTest import QTest
    from drawtemp.studio.r56_qa_lab_qt import GameplayQALabDialog
    QT = True
except ImportError:
    QT = False

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.r40_starters import create_starter_pair

SHA = "a" * 40


@unittest.skipUnless(QT, "Optional PySide6 unavailable")
class QALabQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_dialog(self):
        content, project = create_starter_pair("r40-adventure")
        class Owner(QWidget):
            def __init__(self):
                super().__init__()
                self.session = AuthoringSession(content, project)
                self.focused = None
            def focus_resource(self, key):
                self.focused = key
                return True
        owner = Owner()
        dialog = GameplayQALabDialog(owner)
        dialog.revision.setText(SHA)
        return owner, dialog

    def test_capture_then_batch_and_show_failure_diagnostics(self):
        owner, dialog = self.make_dialog()
        try:
            dialog.case_id.setText("r56b-qt-case")
            dialog.operation.setCurrentIndex(
                dialog.operation.findData("route_realtime_step"))
            dialog.args.setText("[0,0]")
            dialog.path.setText("mode")
            dialog.expected.setText('"campaign"')
            dialog.resource.setCurrentIndex(1)
            dialog.add_step()
            self.assertEqual(len(dialog._draft), 1)
            dialog.capture_case()
            self.assertEqual(dialog.cases.count(), 1)
            self.assertEqual(owner.session.revision, 0)
            dialog.run_cases()
            for _ in range(200):
                if dialog._thread is None:
                    break
                QTest.qWait(30)
            self.assertIsNone(dialog._thread, dialog.status.text())
            self.assertEqual(dialog._batch["counts"]["passed"], 1)
            dialog.cases.setCurrentRow(0)
            dialog.steps.setCurrentRow(1)
            self.assertIn("route_realtime_step", dialog.detail.toPlainText())
            self.assertTrue(dialog.navigate_button.isEnabled())
            dialog.replay_selected()
            for _ in range(200):
                if dialog._thread is None:
                    break
                QTest.qWait(30)
            self.assertIsNone(dialog._thread, dialog.status.text())
            self.assertIn('"status": "reproduced"', dialog.detail.toPlainText())
            self.assertEqual(owner.session.revision, 0)
            self.assertFalse(dialog._batch["release_certified"])
            dialog.navigate_source()
            self.assertEqual(owner.focused, ("project", "", "project"))
        finally:
            if dialog.isVisible():
                dialog.reject()
            owner.close()

    def test_stale_studio_revision_blocks_capture(self):
        owner, dialog = self.make_dialog()
        try:
            dialog._snapshot = type("Stale", (), {"revision": -1})()
            dialog.capture_case()
            self.assertIn("projet a changé", dialog.status.text().lower())
            self.assertEqual(owner.session.revision, 0)
        finally:
            dialog.reject()
            owner.close()


if __name__ == "__main__":
    unittest.main()
