"""R43.B3 Qt offscreen: shared R3 selection/overlays and strict CT read-only."""
import importlib.util
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.ability_authoring_r43 import new_ability

HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.ability_designer_r43_qt import AbilityDesignerDialog
    from drawtemp.studio.ability_targeting_r43_qt import NativeTargetingDialog


@unittest.skipUnless(HAS_QT, "PySide6 optional")
class NativeTargetingQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        c, p = reference_project()
        self.session = AuthoringSession.new(c, p)
        self.caster = next(u for u in c.missions[MISSION].units
                           if u.id == "jeanne")

    def test_shared_qml_viewport_reuses_native_target_area(self):
        spec = new_ability()
        spec["target"].update(team="self", range=0)
        dialog = NativeTargetingDialog(self.session, spec)
        try:
            self.assertEqual(dialog.objectName(), "r43-native-targeting")
            self.assertEqual(dialog.viewport.objectName(), "r43-r3-viewport")
            self.assertEqual(dialog.renderer.scene["mission"], MISSION)
            self.assertEqual(dialog.viewport.rootObject().property(
                "interactionMode"), "select")
            dialog.casters.setCurrentIndex(
                dialog.casters.findData("jeanne"))
            self.assertTrue(dialog.refresh_target(),
                            dialog.diagnostics.toPlainText())
            self.assertIn("jeanne", dialog.diagnostics.toPlainText())
            self.assertIn("intent", dialog.renderer.overlays)
            self.assertEqual(dialog.renderer.overlays["intent"],
                             (tuple(self.caster.pos),))
            self.assertEqual(self.session.revision, 0)
        finally:
            dialog.close()

    def test_invalid_target_and_stale_project_revision_never_write(self):
        spec = new_ability()
        spec["target"].update(team="self", range=0)
        dialog = NativeTargetingDialog(self.session, spec)
        try:
            other = next(cell for cell in reference_project()[0]
                         .missions[MISSION].board.cells()
                         if cell != self.caster.pos)
            dialog.aim_at(*other)
            self.assertIn("Target outside range", dialog.diagnostics.toPlainText())
            self.assertIn("danger", dialog.renderer.overlays)
            self.session.apply(self.session.preview_project(
                lambda doc: {**doc, "title": "Changed"}))
            self.assertFalse(dialog.refresh_target())
            self.assertIn("stale_revision", dialog.diagnostics.toPlainText())
        finally:
            dialog.close()

    def test_parent_ability_designer_ct_mode_gate(self):
        window = AbilityDesignerDialog(self.session)
        try:
            with patch.object(NativeTargetingDialog, "exec", return_value=0):
                self.assertTrue(window.open_native_target(),
                                window.report.toPlainText())
            self.assertEqual(self.session.revision, 0)
            window.draft.document["effects"][0]["formula"] = {
                "op": "stat", "name": "attack"}
            window._load_effect(0)
            self.assertFalse(window.open_native_target())
            self.assertIn("unsupported_formula", window.report.toPlainText())
            self.assertEqual(self.session.revision, 0)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
