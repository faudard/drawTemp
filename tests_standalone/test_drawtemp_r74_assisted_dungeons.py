"""R74.A headless regression: no hidden edits, distinct solved proposals and leases."""
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.procgen import ProcGenError
from drawtemp.sdk.procgen_prefabs import demo_library, verify_with_prefabs
from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.roguelite import EXTENSION
from drawtemp.studio.r74_assisted_dungeons import (
    AssistedDungeonController, DungeonAssistError,
)


class AssistedDungeonTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()
        self.session = AuthoringSession.new(self.content, self.project)
        self.assistant = AssistedDungeonController(self.session)
        self.initial = self.session.snapshot().to_dict()

    def variants(self, **overrides):
        params = {"seed": 71, "count": 3, "rooms": 8, "branches": 2,
                  "locked_goal": True, "biome": "ruins"}
        params.update(overrides)
        return self.assistant.preview_variants(**params)

    def test_three_distinct_proven_logical_topologies_without_writes(self):
        proposals = self.variants()
        self.assertEqual(len(proposals), 3)
        self.assertEqual(len({p.topology_digest for p in proposals}), 3)
        self.assertEqual(len({p.seed for p in proposals}), 3)
        self.assertEqual(self.session.snapshot().to_dict(), self.initial)
        for proposal in proposals:
            doc = proposal.to_dict()
            self.assertTrue(doc["logical_route_verified"])
            self.assertFalse(doc["physical_route_verified"])
            self.assertFalse(doc["player_export_certified"])
            self.assertFalse(doc["applied"])
            self.assertEqual(doc["provenance"]["rights_status"], "no_external_assets")
            self.assertTrue(proposal.layout["route"])
            self.assertTrue(verify_with_prefabs(
                proposal.recipe, demo_library(), proposal.layout, biome="ruins"
            ))

    def test_reproducible_seed_variants_and_detached_report(self):
        first = [p.to_dict() for p in self.variants()]
        other = AssistedDungeonController(
            AuthoringSession.new(self.content, self.project)
        )
        second = [p.to_dict() for p in other.preview_variants(
            seed=71, count=3, rooms=8, branches=2, locked_goal=True
        )]
        self.assertEqual(first, second)
        report = self.assistant._suggestions[0].to_dict()
        report["layout"]["rooms"][0]["role"] = "edited"
        self.assertNotEqual(
            report["layout"]["rooms"][0],
            self.assistant._suggestions[0].layout["rooms"][0],
        )

    def test_selection_is_explicit_one_undoable_project_edit(self):
        proposal = self.variants()[1]
        plan = self.assistant.prepare_selection(proposal)
        self.assertEqual(self.session.snapshot().to_dict(), self.initial)
        self.assertEqual(plan.kind, "r34-roguelite-project")
        transition = self.assistant.apply(proposal)
        applied = transition.snapshot.to_dict()
        self.assertEqual(applied["content"], self.initial["content"])
        self.assertNotEqual(applied["project"], self.initial["project"])
        self.assertEqual(applied["project"]["extensions"][EXTENSION]["data"]["recipe"]["seed"],
                         proposal.seed)
        self.assertEqual(self.session.undo().snapshot.to_dict()["project"],
                         self.initial["project"])
        self.assertEqual(self.session.redo().snapshot.to_dict()["project"],
                         applied["project"])

    def test_reject_does_not_edit_history_or_disk(self):
        proposals = self.variants()
        self.assistant.reject()
        self.assertEqual(self.session.snapshot().to_dict(), self.initial)
        with self.assertRaises(DungeonAssistError) as rejected:
            self.assistant.apply(proposals[0])
        self.assertEqual(rejected.exception.code, "stale_suggestion")

    def test_mutated_proposal_fails_closed(self):
        proposal = self.variants()[0]
        proposal.layout["rooms"][0]["role"] = "goal"
        with self.assertRaises(DungeonAssistError) as rejected:
            self.assistant.apply(proposal)
        self.assertEqual(rejected.exception.code, "modified_suggestion")
        self.assertEqual(self.session.snapshot().to_dict(), self.initial)

    def test_provenance_and_reward_tamper_is_rejected(self):
        proposal = self.variants()[0]
        proposal.provenance["meta_reward"] = 777
        with self.assertRaises(DungeonAssistError) as rejected:
            self.assistant.apply(proposal)
        self.assertEqual(rejected.exception.code, "modified_suggestion")
        self.assertEqual(self.session.snapshot().to_dict(), self.initial)

    def test_project_revision_invalidates_preview(self):
        proposal = self.variants()[0]
        from drawtemp.sdk.roguelite_authoring import preview_roguelite_project
        plan = preview_roguelite_project(
            self.session, proposal.recipe, demo_library(), biome="ruins"
        )
        self.session.apply(plan)
        with self.assertRaises(AuthoringError) as rejected:
            self.assistant.prepare_selection(proposal)
        self.assertEqual(rejected.exception.code, "stale_revision")

    def test_external_prefab_reference_requires_verified_rights(self):
        library = demo_library()
        library["prefabs"][0]["mission_id"] = MISSION
        assistant = AssistedDungeonController(self.session, library)
        with self.assertRaises(DungeonAssistError) as rejected:
            assistant.preview_variants(seed=7)
        self.assertEqual(rejected.exception.code, "rights_unverified")
        self.assertEqual(self.session.snapshot().to_dict(), self.initial)

    def test_rejects_duplicate_only_topologies_and_invalid_limits(self):
        with self.assertRaises(DungeonAssistError) as rejected:
            self.variants(rooms=3, branches=0, locked_goal=False)
        self.assertEqual(rejected.exception.code, "insufficient_variants")
        self.assertEqual(self.assistant._suggestions, ())
        for params in ({"seed": True}, {"count": 0}, {"count": 6},
                       {"rooms": 33}, {"encounter_budget": 65},
                       {"locked_goal": 1}, {"branches": -1}):
            with self.subTest(params=params):
                with self.assertRaises(DungeonAssistError):
                    self.variants(**params)
        self.assertEqual(self.session.snapshot().to_dict(), self.initial)

    def test_unreachable_key_recipe_refused_before_returning_partial_set(self):
        with self.assertRaises(ProcGenError) as rejected:
            self.variants(branches=0, locked_goal=True)
        self.assertEqual(rejected.exception.code, "unsatisfiable_recipe")
        self.assertEqual(self.assistant._suggestions, ())


if __name__ == "__main__":
    unittest.main()
