"""Opt-in Qt offscreen smoke for R51.B; not onscreen / physical GPU certification."""
import os
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r51_layout_authoring import LayoutAuthoring
from drawtemp.studio.r51_layout_draft import new_layout


@unittest.skipUnless(os.environ.get("DRAWTEMP_R51_QT_GATE") == "1",
                     "Opt-in Qt gate; set DRAWTEMP_R51_QT_GATE=1")
class R51QtDesignerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # QT_QPA_PLATFORM=offscreen + QT_QUICK_BACKEND=software should be set
        # externally before Qt loads. R51.C still requires genuine onscreen GPU.
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError as exc:
            raise unittest.SkipTest("PySide6 not installed") from exc
        cls.app = QApplication.instance() or QApplication([])

    def test_tree_property_preview_and_one_transaction(self):
        from drawtemp.studio.r51_designer_qt import R51DesignerDialog
        content, project = reference_project()
        session = AuthoringSession.new(content, project)
        author = LayoutAuthoring(session)
        author.apply(author.preview_replace("battle_hud", new_layout()))
        dialog = R51DesignerDialog(session)
        try:
            self.assertEqual(dialog.objectName(), "r51-designer")
            self.assertIsNotNone(dialog.preview.rootObject(),
                                 "Shared R51Layout.qml failed to load")
            self.assertEqual(dialog._layout_id, "battle_hud")
            welcome = dialog.tree.topLevelItem(0).child(0)
            dialog.tree.setCurrentItem(welcome)
            dialog.widget_text.setText("Bonjour, capitaine")
            dialog.update_widget()
            self.assertEqual(session.revision, 1, "Draft must not auto-apply")
            dialog.width_choice.setValue(1250)
            preview = dialog.preview.rootObject().property("projection")
            self.assertEqual(preview["columns"], 2)
            self.assertTrue(preview["sample"])
            dialog.stage()
            self.assertTrue(dialog.apply_button.isEnabled())
            dialog.apply_changes()
            self.assertEqual(session.revision, 2)
            result = author.inspect()["catalog"]["layouts"]["battle_hud"]
            self.assertEqual(result["root"]["children"][0]["text"],
                             "Bonjour, capitaine")
            dialog.undo()
            self.assertEqual(session.revision, 3)
            self.assertEqual(
                author.inspect()["catalog"]["layouts"]["battle_hud"]["root"]
                ["children"][0]["text"], "Interface personnalisable")
            dialog.redo()
            self.assertEqual(session.revision, 4)
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
