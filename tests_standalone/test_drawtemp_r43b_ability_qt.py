"""R43.B1 Qt offscreen smoke: real form, preview, canonical apply and stale gate."""
import importlib.util
import os
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from drawtemp.sdk.ability_contracts import (
    NAMESPACE, catalog_from_project, preview_ability,
)
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.ability_authoring_r43 import new_ability

_HAS_QT = importlib.util.find_spec("PySide6") is not None
if _HAS_QT:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.ability_designer_r43_qt import AbilityDesignerDialog
    from drawtemp.studio.qt_shell import StudioWindow


@unittest.skipUnless(_HAS_QT, "PySide6 optional")
class AbilityDesignerQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.session = AuthoringSession.new(*reference_project())

    def test_visual_create_preview_and_one_atomic_undo(self):
        dialog = AbilityDesignerDialog(self.session)
        try:
            self.assertEqual(dialog.objectName(), "r43-ability-designer")
            self.assertEqual(dialog.identifier.text(), "r43_new")
            self.assertTrue(dialog.apply_button.isEnabled() is False)
            dialog.name.setText("Vent ardent")
            dialog.radius.setValue(1)
            dialog.shape.setCurrentText("diamond")
            dialog.fixed_power.setValue(25)
            self.assertEqual(self.session.revision, 0)
            self.assertTrue(dialog.preview_changes(), dialog.report.toPlainText())
            self.assertTrue(dialog.apply_button.isEnabled())
            self.assertEqual(dialog.target_grid.item(3, 4).text(), "X")
            self.assertTrue(dialog.apply_changes(), dialog.report.toPlainText())
            result = self.session.snapshot().to_dict()
            self.assertEqual(self.session.revision, 1)
            self.assertEqual(catalog_from_project(result["project"])["abilities"][0]["name"],
                             "Vent ardent")
            native = next(row for row in result["content"]["skills"]
                          if row["id"] == "r43_new")
            self.assertEqual(native["effects"][0]["power"], 25)
            self.assertEqual(native["radius"], 1)
            self.session.undo()
            self.assertEqual(catalog_from_project(
                self.session.snapshot().to_dict()["project"])["abilities"], [])
        finally:
            dialog.close()

    def test_edited_preview_becomes_invalid_and_stale_apply_is_refused(self):
        dialog = AbilityDesignerDialog(self.session)
        try:
            self.assertTrue(dialog.preview_changes())
            dialog.cost.setValue(4)
            self.assertFalse(dialog.apply_button.isEnabled())
            self.assertTrue(dialog.preview_changes())
            self.session.apply(self.session.preview_project(
                lambda data: {**data, "title": "External edit"}))
            self.assertFalse(dialog.apply_changes())
            self.assertIn("stale_revision", dialog.report.toPlainText())
            self.assertEqual(self.session.revision, 1)
            self.assertEqual(catalog_from_project(
                self.session.snapshot().to_dict()["project"])["abilities"], [])
        finally:
            dialog.close()

    def test_unsupported_nested_formula_is_not_flattened_to_zero(self):
        spec = new_ability()
        spec["profiles"] = ["ACTION_REALTIME"]
        spec["timing"] = {"ACTION_REALTIME": {"windup": 3, "cooldown": 12}}
        spec["effects"][0]["formula"] = {
            "op": "add", "left": {"op": "constant", "value": 3},
            "right": {"op": "constant", "value": 5}}
        self.session.apply(preview_ability(self.session, spec))
        before = self.session.snapshot().to_dict()
        dialog = AbilityDesignerDialog(self.session)
        try:
            self.assertEqual(dialog.ability_select.count(), 1)
            # The graph is now a first-class editor: unchanged is rejected,
            # but editing other fields must preserve the original AST.
            self.assertFalse(dialog.preview_changes())
            dialog.name.setText("Arbre conservé")
            self.assertTrue(dialog.preview_changes(), dialog.report.toPlainText())
            self.assertEqual(
                dialog.draft.document["effects"][0]["formula"],
                spec["effects"][0]["formula"])
            self.assertEqual(self.session.snapshot().to_dict(), before)
        finally:
            dialog.close()

    def test_shell_and_gameplay_editor_share_one_authoring_session(self):
        with TemporaryDirectory() as tmp:
            settings = QSettings(str(Path(tmp) / "studio.ini"),
                                 QSettings.IniFormat)
            window = StudioWindow(self.session, settings=settings)
            try:
                self.assertIn("r43_ability", window.commands)
                from drawtemp.studio.genre_rules_qt import GenreRulesWorkspace
                gameplay = GenreRulesWorkspace(window.session, parent=window)
                self.assertIs(gameplay.session, window.session)
                with patch.object(AbilityDesignerDialog, "exec", return_value=0):
                    window.open_ability_designer()
                    gameplay.open_r43_designer()
                gameplay.close()
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()
