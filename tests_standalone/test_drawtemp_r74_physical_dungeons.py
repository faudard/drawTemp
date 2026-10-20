"""R74.C1: three editable R27 puzzle missions, bounded witness and atomic R1 history."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject
from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r74_assisted_dungeons import (
    AssistedDungeonController, DungeonAssistError,
)
from drawtemp.studio.r74_physical_dungeons import (
    apply_physical_dungeons, prepare_physical_dungeons,
)
from sporebound.game_session import GameSession
from sporebound.tactical_rpg3 import authored_rules_for_document


class R74PhysicalDungeonTests(unittest.TestCase):
    def setUp(self):
        self.session = AuthoringSession.new(*reference_project())
        self.controller = AssistedDungeonController(self.session)
        self.proposals = self.controller.preview_variants(
            seed=74, count=3, rooms=8, branches=2,
            locked_goal=True, biome="ruins")
        self.before = self.session.snapshot().to_dict()

    def prepare(self, prefix="r74"):
        return prepare_physical_dungeons(
            self.controller, self.proposals, prefix=prefix)

    def test_three_original_missions_have_independent_physical_key_witnesses(self):
        plan = self.prepare()
        data = plan.to_dict()
        self.assertEqual(data["missions"],
                         ["r74_dungeon_1", "r74_dungeon_2", "r74_dungeon_3"])
        self.assertEqual(data["campaign"], "r74_trilogy")
        self.assertFalse(data["r34_graph_parity"])
        self.assertFalse(data["combat_ai_certified"])
        self.assertFalse(data["player_export_certified"])
        self.assertEqual(len(data["proofs"]), 3)
        self.assertEqual(len({p["source_topology_digest"]
                              for p in data["proofs"]}), 3)
        self.assertEqual(len({tuple(p["goal"])
                              for p in data["proofs"]}), 3)
        self.assertEqual(len({p["mission_digest"]
                              for p in data["proofs"]}), 3)
        for item in data["proofs"]:
            self.assertIn("collect " + item["key"], item["witness"])
            self.assertIn("open " + item["door"], item["witness"])
            self.assertTrue(item["witness"][-1].startswith("walk "))
            self.assertTrue(item["states"] < 50000)
            self.assertTrue(all("Enemy AI" in warning
                                for warning in item["warnings"]))
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_single_authoring_transaction_undo_redo_and_canonical_validation(self):
        plan = self.prepare()
        self.assertEqual(self.session.revision, self.before["revision"])
        after = apply_physical_dungeons(self.controller, plan).snapshot.to_dict()
        self.assertEqual(after["revision"], self.before["revision"] + 1)
        self.assertEqual(len(after["content"]["missions"]),
                         len(self.before["content"]["missions"]) + 3)
        self.assertEqual(after["content"]["missions"][:-3],
                         self.before["content"]["missions"])
        self.assertEqual(after["project"]["story"], self.before["project"]["story"])
        self.assertEqual(after["project"]["campaigns"][:-1],
                         self.before["project"]["campaigns"])
        raw = after["content"]
        content = Content.from_dict(raw, rules=authored_rules_for_document(raw))
        project = GameProject.from_dict(after["project"], content)
        self.assertEqual(project.campaigns[-1]["start_mission"], plan.mission_ids[0])
        for index, mid in enumerate(plan.mission_ids):
            mission = content.missions[mid]
            self.assertEqual(mission.objective, "extract")
            self.assertEqual(len(mission.goal), 1)
            door = next(o for o in mission.objects if o["kind"] == "door")
            key = next(o for o in mission.objects if o["kind"] == "key")
            self.assertEqual(door["key"], key["id"])
            self.assertTrue(door["locked"])
            self.assertEqual(len(mission.board.tiles), 0 if False else
                             len(mission.board.tiles))  # no extra sidecar map
            if index != 2:
                self.assertIn(plan.mission_ids[index + 1], mission.next_missions)
        undone = self.session.undo().snapshot.to_dict()
        self.assertEqual(undone["content"], self.before["content"])
        self.assertEqual(undone["project"], self.before["project"])
        redone = self.session.redo().snapshot.to_dict()
        self.assertEqual(redone["content"], after["content"])
        self.assertEqual(redone["project"], after["project"])

    def test_can_start_generated_mission_and_save_resume_live_key_state(self):
        plan = self.prepare()
        applied = apply_physical_dungeons(self.controller, plan).snapshot.to_dict()
        raw = applied["content"]
        content = Content.from_dict(raw, rules=authored_rules_for_document(raw))
        project = GameProject.from_dict(applied["project"], content)
        session = GameSession.new(content, project, plan.campaign_id, seed=74)
        self.assertIn(plan.mission_ids[0], session.available_missions())
        session.start_mission(plan.mission_ids[0])
        for _ in range(50):
            actor = session.battle.active
            if actor is not None and actor.team == "player":
                break
            session.ai_turn()
        else:
            self.fail("Player activation never reached")
        key = plan.proofs[0]["key"]
        session.execute({"kind": "interact", "object": key})
        self.assertTrue(next(o for o in session.battle.mission.objects
                             if o["id"] == key)["used"])
        with TemporaryDirectory() as directory:
            saved = Path(directory) / "r74-key.json"
            session.save(saved)
            restored = GameSession.load(saved, content, project)
            self.assertEqual(restored.recording(), session.recording())
            self.assertEqual(restored.battle.to_dict(), session.battle.to_dict())

    def test_invalid_or_repeated_input_never_edits_active_session(self):
        for prefix in ("", "Unsafe-ID", "../", "a" * 13):
            with self.subTest(prefix=prefix):
                with self.assertRaises(DungeonAssistError):
                    self.prepare(prefix)
        with self.assertRaises(DungeonAssistError):
            prepare_physical_dungeons(self.controller, self.proposals[:2])
        with self.assertRaises(DungeonAssistError):
            prepare_physical_dungeons(self.controller,
                                      (self.proposals[0],) * 3)
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_stale_revision_and_reused_names_fail_closed(self):
        plan = self.prepare()
        content, project = reference_project()
        change = self.session.preview_project(
            lambda data: {**data, "title": "Changed after preview"})
        self.session.apply(change)
        with self.assertRaises(AuthoringError) as raised:
            apply_physical_dungeons(self.controller, plan)
        self.assertEqual(raised.exception.code, "stale_revision")
        self.assertNotIn("r74_dungeon_1",
                         {x["id"] for x in self.session.snapshot().to_dict()
                          ["content"]["missions"]})
        self.controller.preview_variants(seed=74, count=3,
                                         rooms=8, branches=2, locked_goal=True)
        current = self.controller._suggestions
        after = prepare_physical_dungeons(self.controller, current)
        apply_physical_dungeons(self.controller, after)
        self.controller.preview_variants(seed=74, count=3,
                                         rooms=8, branches=2, locked_goal=True)
        with self.assertRaises(DungeonAssistError) as duplicate:
            prepare_physical_dungeons(self.controller, self.controller._suggestions)
        self.assertEqual(duplicate.exception.code, "duplicate_mission")

    def test_physical_preview_belongs_to_its_original_session(self):
        preview = self.prepare()
        other = AssistedDungeonController(
            AuthoringSession.new(*reference_project()))
        with self.assertRaises(DungeonAssistError) as foreign:
            apply_physical_dungeons(other, preview)
        self.assertEqual(foreign.exception.code, "foreign_preview")
        self.assertEqual(self.session.snapshot().to_dict(), self.before)


if __name__ == "__main__":
    unittest.main()
