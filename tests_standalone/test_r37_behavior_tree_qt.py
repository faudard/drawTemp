"""R37.C offscreen Qt editing and debugging smoke without gameplay mutations."""
import importlib.util
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.advanced_ai import EXTENSION
from tests_standalone.test_r37_ai_session import realtime_fixture

_HAS_QT = importlib.util.find_spec("PySide6") is not None
if _HAS_QT:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.ai_tree_qt import BehaviorTreeDialog


@unittest.skipUnless(_HAS_QT, "PySide6 is an optional Qt Studio dependency")
class BehaviorTreeQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_visual_tree_authoring_preview_apply_and_undo(self):
        content, project = realtime_fixture()
        author = AuthoringSession.new(content, project)
        dialog = BehaviorTreeDialog(author)
        self.assertEqual(dialog.objectName(), "r37-behavior-dialog")
        self.assertEqual(dialog.agent.count(), 1)
        self.assertEqual(dialog.tree.topLevelItemCount(), 1)
        self.assertEqual(dialog.tree.topLevelItem(0).text(0), "root")
        dialog.action.setText("patrol")
        dialog.add_node("action")
        self.assertEqual(author.revision, 0)
        self.assertEqual(len(dialog.draft.document()["nodes"]), 3)
        dialog.preview()
        self.assertEqual(dialog.last_report["action"], "wait")
        dialog.step()
        self.assertIn("cursor", dialog.diagnostics.toPlainText())
        dialog.toggle_breakpoint()
        self.assertTrue(dialog.breakpoints)
        dialog.resume()
        self.assertIn("resume", dialog.diagnostics.toPlainText())
        dialog.apply()
        self.assertEqual(author.revision, 1)
        modified = author.snapshot().to_dict()["project"]["extensions"][
            EXTENSION]["data"]["agents"][0]
        self.assertIn("tree", modified)
        self.assertNotIn("policies", modified)
        dialog.undo()
        self.assertEqual(author.revision, 2)
        reverted = author.snapshot().to_dict()["project"]["extensions"][
            EXTENSION]["data"]["agents"][0]
        self.assertIn("policies", reverted)
        dialog.redo()
        self.assertEqual(author.revision, 3)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
