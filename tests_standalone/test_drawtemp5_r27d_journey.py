"""R27.D campaign journey gates: actual mission actions, saves, and rollback."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject, RuleError
from drawtemp.studio.dungeon_journey import (
    build_dungeon_journey, journey_status,
)
from drawtemp.studio.map_authoring import MapStudio
from sporebound.game_session import GameSession
from sporebound.model import distance
from sporebound.tactical_rpg3 import authored_rules_for_document


class R27DungeonJourneyTests(unittest.TestCase):
    def setUp(self):
        self.maps = MapStudio.reference()
        self.before = self.maps.snapshot()
        self.created = build_dungeon_journey(self.maps, prefix="amber")
        docs = self.maps.snapshot()
        raw = docs["content"]
        self.content = Content.from_dict(
            raw, rules=authored_rules_for_document(raw))
        self.project = GameProject.from_dict(docs["project"], self.content)
        self.ids = self.created["missions"]
        self.campaign = self.created["campaign_id"]

    def session(self):
        return GameSession.new(
            self.content, self.project, self.campaign, seed=17)

    def test_atomic_authoring_one_undo_and_original_project_preserved(self):
        self.assertEqual(self.maps.snapshot()["revision"],
                         self.before["revision"] + 1)
        self.assertEqual(self.maps.mission_id, self.ids["village"])
        self.assertEqual(self.maps.snapshot()["project"]["story"],
                         self.before["project"]["story"])
        self.assertEqual(self.maps.snapshot()["content"]["missions"][
                         :len(self.before["content"]["missions"])],
                         self.before["content"]["missions"])
        graph = set(self.created["missions"].values())
        self.assertTrue(graph <= set(self.maps.map_ids()))
        self.maps.undo()
        self.assertEqual(self.maps.snapshot()["content"],
                         self.before["content"])
        self.assertEqual(self.maps.snapshot()["project"],
                         self.before["project"])
        self.maps.redo()
        self.assertTrue(graph <= set(self.maps.map_ids()))

    def test_journey_has_reachable_locked_room_and_real_boss(self):
        d = self.content.missions[self.ids["dungeon"]]
        self.assertEqual(d.objective, "extract")
        self.assertEqual(d.goal, [(8, 5)])
        door = next(o for o in d.objects if o["id"] == "room_door")
        key = next(o for o in d.objects if o["kind"] == "key")
        self.assertEqual(door["key"], key["id"])
        self.assertTrue(door["locked"])
        self.assertEqual(d.board.tile((7, 3)).blocked, True)
        self.assertIn(self.ids["boss"], d.next_missions)
        self.assertIn(self.ids["return"],
                      self.content.missions[self.ids["boss"]].next_missions)
        boss = self.content.missions[self.ids["boss"]]
        self.assertEqual(boss.objective, "eliminate")
        self.assertTrue(any(u.team == "enemy"
                            and u.name == "Gardien du sanctuaire"
                            for u in boss.units))
        session = self.session()
        self.assertEqual(session.available_missions(),
                         [self.ids["village"]])
        with self.assertRaises(RuleError):
            session.start_mission(self.ids["boss"])

    def _return(self, session):
        self.assertTrue(session.finalized)
        session.return_to_campaign()
        self.assertIsNone(session.battle)

    def _next_hero(self, session):
        for _ in range(50):
            if session.finalized:
                self.fail("Battle ended before the required hero action")
            actor = session.battle.active
            if actor is not None and actor.team == "player":
                return actor
            session.ai_turn()
        self.fail("A player activation did not arrive")

    def _leave_village(self, session):
        session.start_mission(self.ids["village"])
        self._next_hero(session)
        session.execute({"kind": "move", "cell": [2, 14]})
        self._return(session)
        self.assertIn(self.ids["dungeon"], session.available_missions())

    def test_real_village_to_dungeon_key_gate_and_save_resume(self):
        session = self.session()
        self._leave_village(session)
        before_gate = journey_status(session, self.campaign, prefix="amber")
        self.assertTrue(before_gate["stages"]["village"]["completed"])
        self.assertFalse(before_gate["stages"]["boss"]["unlocked"])
        with TemporaryDirectory() as folder:
            checkpoint = Path(folder) / "village.json"
            session.save(checkpoint)
            restored = GameSession.load(checkpoint, self.content, self.project)
            self.assertEqual(restored.recording(), session.recording())
            session = restored
            session.start_mission(self.ids["dungeon"])
            self._next_hero(session)
            self.assertTrue(session.battle.board.tile((7, 3)).blocked)
            with self.assertRaises(RuleError):
                session.execute({"kind": "interact", "object": "room_door"})
            # Only the collected local key authorizes this dungeon door.
            session.execute({"kind": "interact", "object": "amber_amber_key"})
            self.assertTrue(next(o for o in session.battle.mission.objects
                                 if o["kind"] == "key")["used"])
            checkpoint = Path(folder) / "dungeon.json"
            session.save(checkpoint)
            replayed = GameSession.load(checkpoint, self.content, self.project)
            self.assertEqual(replayed.recording(), session.recording())
            session = replayed
            session.execute({"kind": "end"})
            self._next_hero(session)
            session.execute({"kind": "move", "cell": [7, 2]})
            session.execute({"kind": "interact", "object": "room_door"})
            self.assertFalse(session.battle.board.tile((7, 3)).blocked)
            session.execute({"kind": "end"})
            self._next_hero(session)
            session.execute({"kind": "move", "cell": [8, 5]})
            self._return(session)
            after = journey_status(session, self.campaign, prefix="amber")
            self.assertTrue(after["stages"]["dungeon"]["completed"])
            self.assertTrue(after["stages"]["boss"]["available"])
            self.assertEqual(
                session.progress.story_flags["amber_dungeon_cleared"], True)
            self.assertEqual(
                session.progress.flow_ledger.count(
                    self.ids["dungeon"] + ":victory"), 1)
            checkpoint = Path(folder) / "after-dungeon.json"
            session.save(checkpoint)
            self.assertEqual(
                GameSession.load(checkpoint, self.content, self.project)
                .recording(), session.recording())

    def test_second_campaign_is_isolated_from_original_story_and_unlocks(self):
        original = self.project.new_game("main", self.content)
        self.assertNotIn(self.ids["village"], original.unlocked)
        self.assertNotIn(self.ids["boss"], original.unlocked)
        session = self.session()
        self.assertFalse(session.progress.story_pending)
        self.assertFalse(journey_status(session, self.campaign,
                                       prefix="amber")["completed"])

    def test_duplicate_prefix_and_invalid_prefix_never_mutate_documents(self):
        snapshot = self.maps.snapshot()
        with self.assertRaises(RuleError):
            build_dungeon_journey(self.maps, prefix="amber")
        with self.assertRaises(RuleError):
            build_dungeon_journey(self.maps, prefix="../bad")
        self.assertEqual(self.maps.snapshot(), snapshot)

    def test_two_file_save_open_and_project_round_trip(self):
        with TemporaryDirectory() as folder:
            target = Path(folder) / "amber.json"
            self.maps.save_as(target)
            reopened = MapStudio.open(target)
            docs = reopened.snapshot()
            self.assertEqual(docs["content"],
                             self.maps.snapshot()["content"])
            self.assertEqual(docs["project"],
                             self.maps.snapshot()["project"])
            self.assertEqual(docs["dirty"], False)
            state = GameSession.new(
                self.content, self.project, self.campaign, seed=17)
            self.assertIn(self.ids["village"], state.available_missions())


if __name__ == "__main__":
    unittest.main()
