"""3.7.24C: authored world-road interruptions use the canonical StoryBook."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import (GameSession, IncompatibleSaveError,
                                     gameplay_project_digest)
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController
from sporebound.world_map import default_world
from sporebound.world_travel import STEPS_PER_EDGE


class WorldRoadEventTests(TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.project.world = default_world(self.content, self.project.campaigns)
        self.start = self.project.campaigns[0]["start_mission"]
        self.destination = self.content.missions[self.start].next_missions[0]
        self.project.story = {
            "scenes": [{
                "id": "road_merchants", "title": "Marchands sur la route",
                "speaker": "Marchand", "text": "Des bandits nous encerclent.",
                "choices": [
                    {"id": "help", "label": "Proteger les marchands",
                     "effects": [{"kind": "add_flag",
                                  "flag": "road_escort", "amount": 1}]},
                    {"id": "ignore", "label": "Continuer",
                     "effects": [{"kind": "set_flag",
                                  "flag": "road_ignored", "value": True}]},
                ],
            }],
        }
        self.project.world["events"] = [{
            "id": "merchants", "from": self.start,
            "to": self.destination, "scene": "road_merchants",
        }]
        self.project.validate(self.content)

    def new_session(self):
        session = GameSession.new(self.content, self.project, "main")
        session.progress.unlocked.append(self.destination)
        return session

    def test_route_event_interrupts_midway_and_choice_changes_campaign(self):
        session = self.new_session()
        session.world_destination(self.destination)
        for _ in range(STEPS_PER_EDGE // 2):
            session.world_advance()
        self.assertEqual(session.active_scene()["id"], "road_merchants")
        midpoint = session.world_state()
        self.assertEqual(midpoint["step"], STEPS_PER_EDGE // 2)
        self.assertTrue(session.progress.story_flags["world_evt_merchants"])
        self.assertEqual(session.available_missions(), [])
        checkpoint = session.recording()
        restored = GameSession.from_recording(checkpoint, self.content, self.project)
        self.assertEqual(restored.world_state(), midpoint)
        self.assertEqual(restored.active_scene()["id"], "road_merchants")
        before = deepcopy(restored.recording())
        with self.assertRaises(RuleError):
            restored.world_advance()
        self.assertEqual(restored.recording(), before)
        self.assertEqual(
            {row["id"] for row in restored.available_choices()}, {"help", "ignore"})
        restored.choose_story_option("help")
        self.assertIsNone(restored.active_scene())
        self.assertEqual(restored.progress.story_flags["road_escort"], 1)
        self.assertEqual(restored.progress.story_history[-1],
                         {"scene": "road_merchants", "choice": "help"})
        for _ in range(STEPS_PER_EDGE // 2):
            restored.world_advance()
        self.assertEqual(restored.world_state()["at"], self.destination)
        self.assertFalse(restored.world_state()["traveling"])
        self.assertTrue(restored.world_can_enter(self.destination))
        # Road encounters happen once, even on the return journey.
        restored.world_destination(self.start)
        for _ in range(STEPS_PER_EDGE):
            restored.world_advance()
        self.assertIsNone(restored.active_scene())
        self.assertEqual(len(restored.progress.story_history), 1)

    def test_condition_uses_existing_narrative_matches(self):
        self.project.world["events"][0]["when"] = {"flag": "road_permit", "eq": True}
        self.project.validate(self.content)
        session = self.new_session()
        session.world_destination(self.destination)
        for _ in range(STEPS_PER_EDGE):
            session.world_advance()
        self.assertIsNone(session.active_scene())
        self.assertNotIn("world_evt_merchants", session.progress.story_flags)
        session.progress.story_flags["road_permit"] = True
        session.world_destination(self.start)
        for _ in range(STEPS_PER_EDGE // 2):
            session.world_advance()
        self.assertEqual(session.active_scene()["id"], "road_merchants")

    def test_invalid_event_manifest_is_rejected(self):
        example = deepcopy(self.project.world["events"][0])
        cases = [
            [{"id": "bad/id", **{k: v for k, v in example.items() if k != "id"}}],
            [{**example, "from": self.destination, "to": self.destination}],
            [{**example, "scene": "missing"}],
            [{**example, "to": "missing"}],
            [{**example, "when": {"flag": "x", "unknown": 3}}],
            [example, {**example, "id": "again"}],
            [example, example],
        ]
        for events in cases:
            invalid = deepcopy(self.project)
            invalid.world["events"] = events
            with self.subTest(events=events), self.assertRaises(RuleError):
                invalid.validate(self.content)
        self.project.validate(self.content)

    def test_decorative_changes_remain_compatible_but_events_do_not(self):
        baseline = deepcopy(self.project)
        digest = gameplay_project_digest(baseline)
        baseline.world["nodes"][0]["x"] += 1
        baseline.validate(self.content)
        self.assertEqual(gameplay_project_digest(baseline), digest)
        baseline.world["events"][0]["id"] = "different"
        baseline.validate(self.content)
        self.assertNotEqual(gameplay_project_digest(baseline), digest)
        session = self.new_session()
        with self.assertRaises(IncompatibleSaveError):
            GameSession.from_recording(session.recording(), self.content, baseline)
        no_events = deepcopy(self.project)
        no_events.world.pop("events")
        self.assertNotEqual(gameplay_project_digest(self.project),
                            gameplay_project_digest(no_events))
        # No authored events: old decorative-only world saves still hash alike.
        no_world = deepcopy(no_events)
        no_world.world = {}
        self.assertEqual(gameplay_project_digest(no_events),
                         gameplay_project_digest(no_world))

    def test_player_controller_save_recovers_paused_event(self):
        with TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile.json"
            controller = PlayerController(self.content, self.project, profile)
            controller.new_game("main", 1)
            controller.session.progress.unlocked.append(self.destination)
            controller.save()
            controller.world_destination(self.destination)
            for _ in range(STEPS_PER_EDGE // 2):
                controller.world_advance()
            second = PlayerController(self.content, self.project, profile)
            second.load_game("main", 1)
            self.assertEqual(second.session.active_scene()["id"], "road_merchants")
            second.choose_story_option("ignore")
            self.assertTrue(second.session.progress.story_flags["road_ignored"])
            for _ in range(STEPS_PER_EDGE // 2):
                second.world_advance()
            third = PlayerController(self.content, self.project, profile)
            third.load_game("main", 1)
            self.assertEqual(third.session.world_state()["at"], self.destination)
            self.assertTrue(third.session.progress.story_flags["road_ignored"])
