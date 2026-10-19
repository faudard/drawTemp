"""R43.B2 Qt offscreen: formula tree editing and Studio draft integration."""
import importlib.util
import os
import unittest
from copy import deepcopy
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.ability_contracts import catalog_from_project
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.ability_formula_graph_r43 import replace_node

_HAS_QT = importlib.util.find_spec("PySide6") is not None
if _HAS_QT:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QDialog
    from drawtemp.studio.ability_designer_r43_qt import AbilityDesignerDialog
    from drawtemp.studio.ability_formula_graph_r43_qt import FormulaGraphDialog


@unittest.skipUnless(_HAS_QT, "PySide6 optional")
class FormulaGraphQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.session = AuthoringSession.new(*reference_project())

    def test_tree_operator_ports_live_evaluation_and_cancel(self):
        source = {"op": "constant", "value": 8}
        original = deepcopy(source)
        window = FormulaGraphDialog(source)
        try:
            self.assertEqual(window.objectName(), "r43-formula-graph")
            self.assertEqual(window.tree.topLevelItemCount(), 1)
            window.operator.setCurrentText("percent")
            window.amount.setValue(150)
            self.assertTrue(window.replace_selected(),
                            window.diagnostics.toPlainText())
            self.assertEqual(window.tree.topLevelItem(0).childCount(), 1)
            child = window.tree.topLevelItem(0).child(0)
            window.tree.setCurrentItem(child)
            window.operator.setCurrentText("stat")
            window.stat.setCurrentText("magic")
            self.assertTrue(window.replace_selected(),
                            window.diagnostics.toPlainText())
            self.assertIn("Référence: 18", window.diagnostics.toPlainText())
            self.assertEqual(source, original)
            window.reject()
            self.assertIsNone(window.result_formula)
        finally:
            window.close()

    def test_explicit_apply_graph_uses_only_parent_authoring_preview(self):
        dialog = AbilityDesignerDialog(self.session)
        try:
            self.assertEqual(self.session.revision, 0)
            graph = FormulaGraphDialog(
                dialog.draft.document["effects"][0]["formula"], parent=dialog)
            graph.operator.setCurrentText("add")
            self.assertTrue(graph.replace_selected())
            child = graph.tree.topLevelItem(0).child(1)
            graph.tree.setCurrentItem(child)
            graph.operator.setCurrentText("constant")
            graph.constant.setValue(7)
            self.assertTrue(graph.replace_selected())
            graph._accept()
            self.assertEqual(graph.result(), QDialog.Accepted)
            constructed = deepcopy(graph.result_formula)
            # CT dynamic formula: intentionally *not* allowed to be applied.
            # This graph remains CT-compatible only when every operator is
            # constant; here we switch the profile explicitly to action.
            dialog.mode_checks["TACTICAL_CT"].setChecked(False)
            dialog.mode_checks["ACTION_REALTIME"].setChecked(True)
            dialog.resource.setCurrentText("stamina")
            with patch.object(FormulaGraphDialog, "exec",
                              return_value=QDialog.Accepted):
                with patch.object(FormulaGraphDialog, "__init__",
                                  autospec=True, side_effect=None) as ctor:
                    pass
            # Integration without UI mocking: emulate dialog's published
            # validated AST and verify parent preview/apply remains sole owner.
            draft = dialog.draft
            draft.document["effects"][0]["formula"] = constructed
            dialog._load_effect(0)
            self.assertTrue(dialog.preview_balance(),
                            dialog.report.toPlainText())
            self.assertFalse(dialog.apply_button.isEnabled())
            self.assertTrue(dialog.preview_changes(),
                            dialog.report.toPlainText())
            self.assertEqual(self.session.revision, 0)
            self.assertEqual(dialog.draft.document["effects"][0]["formula"],
                             constructed)
            self.assertTrue(dialog.apply_changes(), dialog.report.toPlainText())
            saved = catalog_from_project(
                self.session.snapshot().to_dict()["project"])["abilities"][0]
            self.assertEqual(saved["effects"][0]["formula"], constructed)
            self.session.undo()
            self.assertEqual(catalog_from_project(
                self.session.snapshot().to_dict()["project"])["abilities"], [])
            graph.close()
        finally:
            dialog.close()

    def test_ct_dynamic_formulas_remain_unsupported(self):
        dialog = AbilityDesignerDialog(self.session)
        try:
            dialog.draft.document["effects"][0]["formula"] = {
                "op": "stat", "name": "attack"}
            dialog._load_effect(0)
            dialog.name.setText("Dynamic CT denied")
            self.assertFalse(dialog.preview_changes())
            self.assertIn("unsupported_formula", dialog.report.toPlainText())
            self.assertEqual(self.session.revision, 0)
            self.assertTrue(dialog.preview_balance())
            self.assertEqual(self.session.revision, 0)
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
