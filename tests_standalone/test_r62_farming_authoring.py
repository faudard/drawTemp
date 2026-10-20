"""R62.B.1 headless Farm Studio: typed edit, preview, history and R1 integrity."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringSession, AuthoringError
from drawtemp.studio.farming_authoring import (
    FarmDraft, apply_farm_design, preview_farm_design,
)
from sporebound.farming_life import EXTENSION
from sporebound.living_world import EXTENSION as CLOCK_EXTENSION
from sporebound.model import RuleError
from tests_standalone.test_r25_scene_router import scene_fixture
from tests_standalone.test_r35_living_world import fixture as clock_fixture


def equipment_ids(content):
    return sorted(content.equipment)


def valid_crop(content):
    seed, harvest = equipment_ids(content)[:2]
    return {"id": "herbs", "seed_item": seed, "yield_item": harvest,
            "yield_quantity": 2, "grow_days": 2,
            "soils": ["loam"], "seasons": ["spring", "summer"]}


def valid_animal(content):
    seed, harvest = equipment_ids(content)[:2]
    return {"id": "hen", "scene": "arrival", "feed_item": seed,
            "yield_item": harvest, "yield_quantity": 1, "interval_days": 1}


class FarmStudioAuthoringTests(unittest.TestCase):
    def test_new_farm_initializes_r35_only_with_explicit_opt_in(self):
        content, project = scene_fixture()
        session = AuthoringSession(content, project)
        baseline = session.snapshot().to_dict()
        draft = FarmDraft(session)
        self.assertFalse(draft.clock_present)
        draft.upsert("plots", {"id": "field", "scene": "arrival", "soil": "loam"})
        draft.upsert("crops", valid_crop(content))
        draft.upsert("animals", valid_animal(content))
        with self.assertRaises(ValueError):
            draft.preview()
        self.assertEqual(session.snapshot().to_dict(), baseline)
        draft.initialize_clock = True
        preview = draft.preview()
        self.assertEqual(preview.report["plot_count"], 1)
        self.assertEqual(preview.report["crop_count"], 1)
        self.assertEqual(preview.report["animal_count"], 1)
        self.assertTrue(preview.report["clock_initialized"])
        self.assertEqual(session.snapshot().to_dict(), baseline)
        transition = draft.apply()
        self.assertEqual(transition.snapshot.revision, 1)
        persisted = session.snapshot().to_dict()["project"]["extensions"]
        self.assertIn(EXTENSION, persisted)
        self.assertIn(CLOCK_EXTENSION, persisted)
        self.assertEqual(persisted[EXTENSION]["data"]["crops"][0]["id"], "herbs")
        # One project commit, hence one global Undo restores both extensions.
        session.undo()
        undone = session.snapshot().to_dict()["project"].get("extensions", {})
        self.assertNotIn(EXTENSION, undone)
        self.assertNotIn(CLOCK_EXTENSION, undone)
        session.redo()
        self.assertIn(EXTENSION,
                      session.snapshot().to_dict()["project"]["extensions"])

    def test_bounded_draft_history_and_immutable_input(self):
        content, project = clock_fixture()
        session = AuthoringSession(content, project)
        draft = FarmDraft(session, history_limit=2)
        original = session.snapshot().to_dict()
        field = {"id": "field", "scene": "arrival", "soil": "clay"}
        draft.upsert("plots", field)
        field["soil"] = "sand"
        self.assertEqual(draft.document["plots"][0]["soil"], "clay")
        self.assertTrue(draft.can_undo)
        draft.settings(seed=7, season_days=9, weather=True)
        self.assertTrue(draft.undo())
        self.assertEqual(draft.document["seed"], 17)
        self.assertTrue(draft.redo())
        self.assertEqual(draft.document["season_days"], 9)
        draft.undo()
        draft.upsert("plots", {"id": "field", "scene": "arrival", "soil": "loam"},
                     original_id="field")
        self.assertFalse(draft.can_redo)
        with self.assertRaises(RuleError):
            draft.upsert("plots", {"id": "field", "scene": "arrival", "soil": "loam"})
        with self.assertRaises(RuleError):
            draft.upsert("plots", {"id": "renamed", "scene": "arrival",
                                   "soil": "loam"}, original_id="field")
        with self.assertRaises(RuleError):
            draft.remove("animals", "missing")
        self.assertEqual(session.snapshot().to_dict(), original)
        draft.remove("plots", "field")
        self.assertEqual(draft.document["plots"], [])
        draft.undo()
        self.assertEqual(draft.document["plots"][0]["id"], "field")

    def test_invalid_inputs_fail_closed_and_previews_cannot_override_revision(self):
        content, project = clock_fixture()
        session = AuthoringSession(content, project)
        draft = FarmDraft(session)
        prior = draft.document
        errors = [
            ("plots", {"id": "no_scene", "scene": "missing", "soil": "loam"}),
            ("crops", {"id": "invalid", "seed_item": "missing",
                       "yield_item": equipment_ids(content)[0],
                       "yield_quantity": 1, "grow_days": 2,
                       "soils": ["loam"], "seasons": ["spring"]}),
            ("animals", {"id": "hen", "scene": "arrival",
                         "feed_item": equipment_ids(content)[0],
                         "yield_item": equipment_ids(content)[1],
                         "yield_quantity": True, "interval_days": 1}),
        ]
        for family, row in errors:
            with self.subTest(family=family), self.assertRaises(RuleError):
                draft.upsert(family, row)
            self.assertEqual(draft.document, prior)
        with self.assertRaises(RuleError):
            draft.settings(seed=0, season_days=1, weather=True)
        self.assertEqual(draft.document, prior)
        draft.upsert("plots", {"id": "field", "scene": "arrival", "soil": "loam"})
        old_preview = draft.preview()
        session.undo() if session.snapshot().can_undo else None
        # Unrelated canonical transaction changes the revision.
        other = FarmDraft(session)
        other.settings(seed=19, season_days=14, weather=False)
        other.apply()
        with self.assertRaises(ValueError):
            draft.preview()
        with self.assertRaises(AuthoringError):
            apply_farm_design(session, old_preview)
        self.assertEqual(session.snapshot().to_dict()["project"]
                         ["extensions"][EXTENSION]["data"]["seed"], 19)

    def test_existing_r35_schedule_is_preserved_byte_for_byte(self):
        content, project = clock_fixture()
        before_clock = deepcopy(project.extensions[CLOCK_EXTENSION])
        session = AuthoringSession(content, project)
        draft = FarmDraft(session)
        self.assertTrue(draft.clock_present)
        draft.initialize_clock = True  # Cannot replace an existing clock.
        draft.upsert("animals", valid_animal(content))
        preview = draft.preview()
        self.assertFalse(preview.report["clock_initialized"])
        draft.apply()
        persisted = session.snapshot().to_dict()["project"]["extensions"]
        self.assertEqual(persisted[CLOCK_EXTENSION], before_clock)
        self.assertEqual(persisted[EXTENSION]["data"]["animals"][0]["id"], "hen")


if __name__ == "__main__":
    unittest.main()
