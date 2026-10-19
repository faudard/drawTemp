"""R45.B offscreen GUI smoke; onscreen/manual certification remains separate."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.living_world import EXTENSION
from tests_standalone.test_r45_crafting import crafting_fixture

_HAS_QT = importlib.util.find_spec("PySide6") is not None
if _HAS_QT:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.living_economy_qt import LivingEconomyDialog


@unittest.skipUnless(_HAS_QT, "PySide6 optional")
class R45EconomyQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.content, self.project = crafting_fixture()
        self.editor = AuthoringSession.new(self.content, self.project)
        self.dialog = LivingEconomyDialog(self.editor)

    def tearDown(self):
        self.dialog.close()

    def test_shops_recipes_edit_preview_apply_and_undo(self):
        dialog = self.dialog
        self.assertEqual(dialog.shop_list.count(), 1)
        self.assertEqual(dialog.recipe_list.count(), 1)
        self.assertEqual(dialog.shop_header.ident.text(), "village_shop")
        self.assertEqual(dialog.recipe_header.ident.text(), "brew_elixir")
        dialog.shop_items.cellWidget(0, 3).setValue(7)
        dialog._save_shop()
        dialog.recipe_gold.setValue(8)
        dialog._save_recipe()
        self.assertTrue(dialog._preview(), dialog.diagnostics.toPlainText())
        self.assertEqual(self.editor.revision, 0)
        dialog._apply()
        self.assertEqual(self.editor.revision, 1)
        document = self.editor.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"]
        self.assertEqual(document["shops"][0]["items"][0]["daily_stock"], 7)
        self.assertEqual(document["recipes"][0]["gold_cost"], 8)
        self.editor.undo()
        document = self.editor.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"]
        self.assertEqual(document["shops"][0]["items"][0]["daily_stock"], 5)
        self.editor.redo()
        document = self.editor.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"]
        self.assertEqual(document["recipes"][0]["gold_cost"], 8)

    def test_invalid_stock_and_stale_dialog_are_fail_closed(self):
        dialog = self.dialog
        dialog.shop_items.cellWidget(0, 2).setValue(900)
        dialog._save_shop()
        self.assertFalse(dialog._preview())
        self.assertEqual(self.editor.revision, 0)
        from drawtemp.studio.living_economy_authoring import EconomyDraft
        other = EconomyDraft(self.editor)
        changed = dict(other.document["recipes"][0])
        changed["gold_cost"] = 13
        other.upsert_recipe(changed, original_id=changed["id"])
        other.apply()
        dialog._apply()
        self.assertEqual(self.editor.revision, 1)
        self.assertIn("modification appliquée", dialog.diagnostics.toPlainText())

    def test_new_recipe_with_typed_rows_and_delete_without_commit(self):
        dialog = self.dialog
        dialog._new_recipe()
        dialog.recipe_header.ident.setText("healing_tonic")
        dialog.recipe_inputs.append_item({"item": "herb", "quantity": 1})
        dialog.recipe_outputs.append_item({"item": "elixir", "quantity": 1})
        dialog._save_recipe()
        self.assertEqual(dialog.recipe_list.count(), 2)
        self.assertTrue(dialog._preview(), dialog.diagnostics.toPlainText())
        dialog._delete_recipe()
        self.assertEqual(dialog.recipe_list.count(), 1)
        self.assertEqual(self.editor.revision, 0)


if __name__ == "__main__":
    unittest.main()
