"""3.7.24B headless route, access, reload and integrity gates."""
from copy import deepcopy
from unittest import TestCase
from tempfile import TemporaryDirectory
from pathlib import Path

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController
from sporebound.world_map import default_world
from sporebound.world_travel import (AT, GOAL, VIA, STEP, STEPS_PER_EDGE,
                                     WorldJourney)


class ContinuousWorldJourneyTests(TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.project.world = default_world(self.content, self.project.campaigns)
        self.start = self.project.campaigns[0]["start_mission"]
        self.session = GameSession.new(self.content, self.project, "main")

    def _link(self):
        # Use the real authored link, never fabricate an alternative route.
        successors = self.content.missions[self.start].next_missions
        self.assertTrue(successors)
        return successors[0]

    def test_legacy_project_and_partial_world_remain_optional(self):
        legacy = GameProject.default(self.content)
        self.assertNotIn("world", legacy.to_dict())
        self.assertIsNone(GameSession.new(self.content, legacy, "main").world_state())
        self.assertEqual(self.session.world_state()["at"], self.start)
        self.assertEqual(self.session.progress.story_flags, {})

    def test_locked_destination_does_not_mutate_campaign(self):
        destination = self._link()
        before = deepcopy(self.session.recording())
        with self.assertRaises(RuleError):
            self.session.world_destination(destination)
        self.assertEqual(self.session.recording(), before)
        with self.assertRaises(RuleError):
            self.session.world_advance()
        self.assertEqual(self.session.recording(), before)

    def test_route_is_continuous_and_checkpointed_mid_edge(self):
        destination = self._link()
        self.session.progress.unlocked.append(destination)
        journey = self.session.world_destination(destination)
        self.assertTrue(journey["traveling"])
        self.assertEqual(journey["route"], [self.start, destination])
        self.assertFalse(self.session.world_can_enter(destination))
        halfway = None
        for _ in range(STEPS_PER_EDGE // 2):
            halfway = self.session.world_advance()
        self.assertEqual(halfway["via"], destination)
        start_xy = next((row["x"], row["y"]) for row in self.project.world["nodes"]
                        if row["mission"] == self.start)
        self.assertNotEqual(halfway["position"], start_xy)
        snapshot = self.session.recording()
        restored = GameSession.from_recording(snapshot, self.content, self.project)
        self.assertEqual(restored.world_state(), halfway)
        for _ in range(STEPS_PER_EDGE - STEPS_PER_EDGE // 2):
            restored.world_advance()
        final = restored.world_state()
        self.assertEqual(final["at"], destination)
        self.assertFalse(final["traveling"])
        self.assertTrue(restored.world_can_enter(destination))
        self.assertEqual(self.session.world_state()["at"], self.start)

    def test_multi_leg_route_uses_only_accessible_mission_links(self):
        first = self._link()
        second = self.content.missions[first].next_missions[0]
        third = self.content.missions[second].next_missions[0]
        self.session.progress.unlocked.extend([first, second])
        journey = self.session.world_destination(second)
        self.assertEqual(journey["route"], [self.start, first, second])
        self.assertNotIn(third, journey["reachable"])
        with self.assertRaises(RuleError):
            self.session.world_destination(third)
        for _ in range(STEPS_PER_EDGE * 2):
            journey = self.session.world_advance()
        self.assertEqual(journey["at"], second)
        self.assertFalse(journey["traveling"])
        self.assertTrue(self.session.world_can_enter(second))

    def test_reverse_access_and_corrupt_checkpoint(self):
        destination = self._link()
        self.session.progress.unlocked.append(destination)
        self.session.world_destination(destination)
        for _ in range(STEPS_PER_EDGE):
            self.session.world_advance()
        self.session.world_destination(self.start)
        for _ in range(STEPS_PER_EDGE):
            self.session.world_advance()
        self.assertEqual(self.session.world_state()["at"], self.start)
        snapshot = self.session.recording()
        for field, bad in ((AT, "unknown"), (GOAL, "unknown"),
                           (VIA, destination), (STEP, True)):
            tampered = deepcopy(snapshot)
            tampered["progress"]["story_flags"][field] = bad
            from sporebound.game_session import digest
            tampered["digest"] = digest({k: v for k, v in tampered.items()
                                        if k != "digest"})
            with self.subTest(field=field), self.assertRaises(RuleError):
                GameSession.from_recording(tampered, self.content, self.project)

    def test_controller_persists_every_step_and_can_reload(self):
        destination = self._link()
        with TemporaryDirectory() as folder:
            controller = PlayerController(
                self.content, self.project, Path(folder) / "world.json")
            controller.new_game("main", 1)
            controller.session.progress.unlocked.append(destination)
            controller.save()
            controller.world_destination(destination)
            for _ in range(3):
                controller.world_advance()
            expected = controller.session.world_state()
            other = PlayerController(
                self.content, self.project, Path(folder) / "world.json")
            other.load_game("main", 1)
            self.assertEqual(other.session.world_state(), expected)
            self.assertFalse(other.session.world_can_enter(destination))
            for _ in range(STEPS_PER_EDGE - 3):
                other.world_advance()
            self.assertTrue(other.session.world_can_enter(destination))
