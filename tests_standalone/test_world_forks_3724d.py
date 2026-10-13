"""3.7.24D — Multiple encounters per road and choice-directed junctions."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController
from sporebound.world_map import default_world
from sporebound.world_travel import (AT, PENDING, REVERSE, STEP, STEPS_PER_EDGE)


class AuthoredWorldForkTests(TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.content.missions["garden"].next_missions.extend(["hold", "crown"])
        self.project = GameProject.default(self.content)
        self.project.world = default_world(self.content, self.project.campaigns)
        self.project.story = {
            "scenes": [
                {"id": "caravan", "title": "Caravane", "speaker": "Voyageur",
                 "text": "Quelle route prendre ?", "choices": [
                     {"id": "forward", "label": "Continuer"},
                     {"id": "back", "label": "Revenir au carrefour"},
                     {"id": "north", "label": "Vers les collines",
                      "effects": [{"kind": "unlock_mission", "mission": "hold"}]},
                     {"id": "south", "label": "Vers la citadelle",
                      "effects": [{"kind": "unlock_mission", "mission": "crown"}]},
                 ]},
                {"id": "toll", "title": "Peage", "speaker": "Soldat",
                 "text": "Passage controle.", "choices": [
                     {"id": "negotiate", "label": "Negocier",
                      "effects": [{"kind": "set_flag",
                                   "flag": "peage_negocie", "value": True}]},
                     {"id": "pass", "label": "Continuer"},
                 ]},
            ],
        }
        self.project.world["events"] = [
            {"id": "caravan", "from": "garden", "to": "escape",
             "scene": "caravan", "step": 2, "routes": {
                 "forward": {"kind": "continue"},
                 "back": {"kind": "return"},
                 "north": {"kind": "destination", "mission": "hold"},
                 "south": {"kind": "destination", "mission": "crown"},
             }},
            {"id": "toll", "from": "garden", "to": "escape",
             "scene": "toll", "step": 6},
        ]
        self.project.validate(self.content)

    def session(self):
        s = GameSession.new(self.content, self.project, "main")
        s.progress.unlocked.append("escape")
        return s

    def advance(self, session, count):
        result = None
        for _ in range(count):
            result = session.world_advance()
        return result

    def test_two_distinct_events_on_same_road_and_safe_return(self):
        s = self.session()
        s.world_destination("escape")
        self.advance(s, 2)
        self.assertEqual(s.active_scene()["id"], "caravan")
        s.choose_story_option("forward")
        self.assertTrue(s.progress.story_flags["world_evt_caravan"])
        self.advance(s, 4)
        self.assertEqual(s.active_scene()["id"], "toll")
        self.assertEqual(s.world_state()["step"], 6)
        s.choose_story_option("negotiate")
        self.assertTrue(s.progress.story_flags["peage_negocie"])
        self.assertEqual(self.advance(s, 2)["at"], "escape")
        self.assertEqual(len(s.progress.story_history), 2)
        # Once per campaign: no duplicate events in the return direction.
        s.world_destination("garden")
        self.advance(s, STEPS_PER_EDGE)
        self.assertIsNone(s.active_scene())
        self.assertEqual(s.world_state()["at"], "garden")
        self.assertEqual(len(s.progress.story_history), 2)

    def test_return_retraces_pixels_without_teleporting(self):
        s = self.session()
        s.world_destination("escape")
        self.advance(s, 2)
        x_before = s.world_state()["position"]
        s.choose_story_option("back")
        state = s.world_state()
        self.assertTrue(state["reversing"])
        self.assertEqual(state["step"], 2)
        self.assertEqual(state["goal"], "garden")
        after = self.advance(s, 1)
        self.assertEqual(after["step"], 1)
        self.assertNotEqual(after["position"], x_before)
        after = self.advance(s, 1)
        self.assertEqual(after["position"], (next(n["x"] for n in
            self.project.world["nodes"] if n["mission"] == "garden"),
            next(n["y"] for n in self.project.world["nodes"]
                 if n["mission"] == "garden")))
        self.assertFalse(after["traveling"])
        self.assertFalse(after["reversing"])
        # Encounter 2 was not passed and is still available on another trip.
        s.world_destination("escape")
        self.advance(s, 6)
        self.assertEqual(s.active_scene()["id"], "toll")

    def test_two_independent_alternate_branches_and_save_during_reverse(self):
        for choice, destination in (("north", "hold"), ("south", "crown")):
            with self.subTest(choice=choice):
                s = self.session()
                s.world_destination("escape")
                self.advance(s, 2)
                s.choose_story_option(choice)
                state = s.world_state()
                self.assertEqual(state["goal"], destination)
                self.assertEqual(state["step"], 2)
                self.assertTrue(state["reversing"])
                self.assertIn(destination, s.progress.unlocked)
                self.assertNotIn(PENDING, s.progress.story_flags)
                self.advance(s, 1)
                resumed = GameSession.from_recording(
                    s.recording(), self.content, self.project)
                self.assertEqual(resumed.world_state()["step"], 1)
                self.assertTrue(resumed.world_state()["reversing"])
                self.advance(resumed, 1)
                self.assertFalse(resumed.world_state()["reversing"])
                self.assertEqual(resumed.world_state()["at"], "garden")
                self.advance(resumed, STEPS_PER_EDGE)
                self.assertEqual(resumed.world_state()["at"], destination)
                self.assertFalse(resumed.world_state()["traveling"])
                self.assertTrue(resumed.world_can_enter(destination))

    def test_locked_detour_rejects_choice_atomically(self):
        project = deepcopy(self.project)
        project.story["scenes"][0]["choices"][2].pop("effects")
        project.validate(self.content)
        s = GameSession.new(self.content, project, "main")
        s.progress.unlocked.append("escape")
        s.world_destination("escape")
        self.advance(s, 2)
        snapshot = s.recording()
        with self.assertRaises(RuleError):
            s.choose_story_option("north")
        self.assertEqual(s.recording(), snapshot)
        self.assertEqual(s.active_scene()["id"], "caravan")

    def test_reversed_travel_meets_event_at_same_physical_point(self):
        s = self.session()
        s.progress.story_flags[AT] = "escape"
        s.world_destination("garden")
        self.advance(s, 2)  # authored toll at 6 -> reverse step 2
        self.assertEqual(s.active_scene()["id"], "toll")
        s.choose_story_option("pass")
        self.advance(s, 4)  # authored caravan at 2 -> reverse step 6
        self.assertEqual(s.active_scene()["id"], "caravan")
        self.assertEqual(s.world_state()["step"], 6)
        s.choose_story_option("back")
        self.advance(s, 6)
        self.assertEqual(s.world_state()["at"], "escape")

    def test_invalid_event_positions_and_choice_targets(self):
        bad = [
            [{**self.project.world["events"][0], "step": 0}],
            [{**self.project.world["events"][0], "step": True}],
            [{**self.project.world["events"][0], "step": 8}],
            [{**self.project.world["events"][0], "routes": {
                "not_a_choice": {"kind": "return"}}}],
            [{**self.project.world["events"][0], "routes": {
                "north": {"kind": "destination", "mission": "missing"}}}],
            [self.project.world["events"][0],
             {**self.project.world["events"][1], "step": 2}],
        ]
        for events in bad:
            project = deepcopy(self.project)
            project.world["events"] = events
            with self.subTest(events=events), self.assertRaises(RuleError):
                project.validate(self.content)

    def test_controller_checkpoint_in_middle_of_branch_choice(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "campaign.json"
            player = PlayerController(self.content, self.project, path)
            player.new_game("main", 1)
            player.session.progress.unlocked.append("escape")
            player.save()
            player.world_destination("escape")
            for _ in range(2):
                player.world_advance()
            player.choose_story_option("north")
            player.world_advance()
            resumed = PlayerController(self.content, self.project, path)
            resumed.load_game("main", 1)
            self.assertTrue(resumed.session.world_state()["reversing"])
            resumed.world_advance()
            for _ in range(STEPS_PER_EDGE):
                resumed.world_advance()
            self.assertEqual(resumed.session.world_state()["at"], "hold")
