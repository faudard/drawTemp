"""R62.B.2 typed authoring: R35 dependencies, local/global Undo/Redo and stale guards."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringSession, AuthoringError
from drawtemp.studio.relationship_authoring import (
    RelationshipDraft, preview_relationship_design, apply_relationship_design)
from sporebound.model import RuleError
from sporebound.relationship_life import EXTENSION
from sporebound.living_world import EXTENSION as WORLD_EXTENSION
from tests_standalone.test_r35_living_world import fixture as world_fixture
from tests_standalone.test_r25_scene_router import scene_fixture


def merchant_row(content):
    return {
        "npc": "merchant", "initial": 0, "talk_gain": 4,
        "talk_activity": "trade",
        "gifts": [{"item": sorted(content.equipment)[0], "gain": 8}],
    }


class RelationshipAuthoringTests(unittest.TestCase):
    def test_canonical_preview_single_apply_and_global_undo(self):
        content, project = world_fixture()
        session = AuthoringSession(content, project)
        baseline = session.snapshot().to_dict()
        before_clock = deepcopy(project.extensions[WORLD_EXTENSION])
        draft = RelationshipDraft(session)
        self.assertIn("merchant", draft.npcs)
        draft.upsert(merchant_row(content))
        preview = draft.preview()
        self.assertEqual(preview.report["npc_count"], 1)
        self.assertEqual(preview.report["gift_count"], 1)
        self.assertEqual(session.snapshot().to_dict(), baseline)
        transition = draft.apply()
        self.assertEqual(transition.snapshot.revision, 1)
        data = session.snapshot().to_dict()["project"]["extensions"]
        self.assertEqual(data[WORLD_EXTENSION], before_clock)
        self.assertEqual(data[EXTENSION]["data"]["relationships"][0]["npc"], "merchant")
        session.undo()
        self.assertNotIn(EXTENSION, session.snapshot().to_dict()
                         ["project"].get("extensions", {}))
        session.redo()
        self.assertIn(EXTENSION, session.snapshot().to_dict()
                      ["project"]["extensions"])

    def test_draft_edit_delete_history_and_refusal_without_mutation(self):
        content, project = world_fixture()
        session = AuthoringSession(content, project)
        draft = RelationshipDraft(session, history_limit=2)
        first = merchant_row(content)
        draft.upsert(first)
        first["talk_gain"] = 18
        self.assertEqual(draft.document["relationships"][0]["talk_gain"], 4)
        updated = merchant_row(content)
        updated["talk_gain"] = 6
        draft.upsert(updated, original_npc="merchant")
        self.assertTrue(draft.undo())
        self.assertEqual(draft.document["relationships"][0]["talk_gain"], 4)
        self.assertTrue(draft.redo())
        self.assertEqual(draft.document["relationships"][0]["talk_gain"], 6)
        draft.undo()
        with self.assertRaises(RuleError):
            draft.upsert(first)
        with self.assertRaises(RuleError):
            draft.upsert({**first, "npc": "traveler"},
                         original_npc="merchant")
        with self.assertRaises(RuleError):
            draft.upsert({**first, "talk_activity": "missing"},
                         original_npc="merchant")
        with self.assertRaises(RuleError):
            draft.remove("unknown")
        draft.remove("merchant")
        self.assertFalse(draft.can_redo)
        self.assertEqual(draft.document["relationships"], [])
        self.assertEqual(session.revision, 0)

    def test_missing_r35_and_stale_authoring_fail_closed(self):
        content, project = scene_fixture()
        session = AuthoringSession(content, project)
        with self.assertRaises(ValueError):
            RelationshipDraft(session)
        with self.assertRaises(ValueError):
            preview_relationship_design(
                session, {"version": 1, "relationships": []})
        content, project = world_fixture()
        session = AuthoringSession(content, project)
        draft = RelationshipDraft(session)
        draft.upsert(merchant_row(content))
        old_preview = draft.preview()
        other = RelationshipDraft(session)
        other.upsert({**merchant_row(content), "talk_gain": 7})
        other.apply()
        with self.assertRaises(ValueError):
            draft.preview()
        with self.assertRaises(AuthoringError):
            apply_relationship_design(session, old_preview)
        self.assertEqual(session.snapshot().to_dict()["project"]
                         ["extensions"][EXTENSION]["data"]
                         ["relationships"][0]["talk_gain"], 7)


if __name__ == "__main__":
    unittest.main()
