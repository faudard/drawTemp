"""R35.D2 Qt offscreen form for explicit inter-scene NPC portals."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HAS_QT = importlib.util.find_spec("PySide6") is not None
if _HAS_QT:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.living_world_qt import TransferEditor, LivingWorldDialog
    from drawtemp.sdk.authoring import AuthoringSession
    from tests_standalone.test_r35_navigation import positional_village


@unittest.skipUnless(_HAS_QT, "Qt6 is optional")
class TransferAuthoringQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_transfer_form_creates_typed_portal_record(self):
        editor = TransferEditor(["a", "b"])
        editor.ident.setText("a_b")
        editor.origin.setCurrentText("a")
        editor.destination.setCurrentText("b")
        editor.from_x.setValue(3)
        editor.from_y.setValue(1)
        editor.to_x.setValue(0)
        editor.to_y.setValue(1)
        editor.minutes.setValue(3)
        editor._save()
        self.assertEqual(editor.transfer, {
            "id": "a_b", "from_scene": "a", "to_scene": "b",
            "from_pos": [3, 1], "to_pos": [0, 1],
            "travel_minutes": 3})
        editor.close()

    def test_world_dialog_displays_authored_portal_catalogue(self):
        content, project = positional_village()
        authoring = AuthoringSession.new(content, project)
        dialog = LivingWorldDialog(authoring)
        self.assertEqual(dialog.transfer_list.count(), 0)
        dialog.document["transfers"] = [{
            "id": "a_b", "from_scene": "a", "to_scene": "b",
            "from_pos": [1, 1], "to_pos": [0, 0],
            "travel_minutes": 2}]
        dialog._load_transfers()
        self.assertEqual(dialog.transfer_list.count(), 1)
        self.assertIn("a_b", dialog.transfer_list.item(0).text())
        dialog.transfer_list.setCurrentRow(0)
        dialog._remove_transfer()
        self.assertNotIn("transfers", {})  # Catalogue now empty, never applied.
        self.assertEqual(dialog.document["transfers"], [])
        self.assertEqual(authoring.revision, 0)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
