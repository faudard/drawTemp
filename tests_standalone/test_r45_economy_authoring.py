"""R45.B: economy drafts use the real R1 authoring history and strict pairing."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.studio.living_economy_authoring import EconomyDraft
from sporebound.living_world import EXTENSION
from tests_standalone.test_r45_crafting import crafting_fixture


class R45EconomyAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = crafting_fixture()
        self.session = AuthoringSession.new(self.content, self.project)

    def test_preview_apply_undo_redo_one_transaction(self):
        original = self.session.snapshot().to_dict()
        draft = EconomyDraft(self.session)
        self.assertTrue({"elixir", "herb"} <= set(draft.item_ids()))
        item = deepcopy(draft.document["shops"][0])
        item["items"][0]["daily_stock"] = 8
        draft.upsert_shop(item, original_id=item["id"])
        recipe = deepcopy(draft.document["recipes"][0])
        recipe["gold_cost"] = 6
        draft.upsert_recipe(recipe, original_id=recipe["id"])
        plan = draft.preview()
        self.assertEqual(plan.report["source_revision"], 0)
        self.assertEqual(self.session.snapshot().to_dict(), original)
        draft.apply()
        self.assertEqual(self.session.revision, 1)
        document = self.session.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"]
        self.assertEqual(document["shops"][0]["items"][0]["daily_stock"], 8)
        self.assertEqual(document["recipes"][0]["gold_cost"], 6)
        self.session.undo()
        self.assertEqual(self.session.snapshot().to_dict(), original)
        self.session.redo()
        document = self.session.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"]
        self.assertEqual(document["recipes"][0]["gold_cost"], 6)

    def test_stale_revision_after_competing_editor_or_undo(self):
        old = EconomyDraft(self.session)
        other = EconomyDraft(self.session)
        edit = deepcopy(other.document["recipes"][0])
        edit["gold_cost"] = 9
        other.upsert_recipe(edit, original_id=edit["id"])
        other.apply()
        self.session.undo()
        with self.assertRaises((AuthoringError, ValueError)):
            old.apply()  # Revision is monotonic; undo does not un-stale it.

    def test_invalid_draft_is_rejected_without_mutation(self):
        original = self.session.snapshot().to_dict()
        draft = EconomyDraft(self.session)
        shop = deepcopy(draft.document["shops"][0])
        shop["items"][0]["sell_price"] = 999
        draft.upsert_shop(shop, original_id=shop["id"])
        with self.assertRaises(AuthoringError):
            draft.preview()
        self.assertEqual(self.session.snapshot().to_dict(), original)

    def test_catalogue_deletions_and_identity_guards(self):
        draft = EconomyDraft(self.session)
        value = deepcopy(draft.document["recipes"][0])
        with self.assertRaises(ValueError):
            draft.upsert_recipe(value)
        renamed = deepcopy(value)
        renamed["id"] = "other"
        with self.assertRaises(ValueError):
            draft.upsert_recipe(renamed, original_id=value["id"])
        with self.assertRaises(ValueError):
            draft.remove_shop("not-a-shop")
        draft.remove_shop("village_shop")
        if not {"herb", "elixir"} & set(self.content.equipment):
            with self.assertRaises(AuthoringError):
                draft.preview()  # Recipe references now have no item source.
        else:
            self.assertEqual(draft.document["shops"], [])


if __name__ == "__main__":
    unittest.main()
