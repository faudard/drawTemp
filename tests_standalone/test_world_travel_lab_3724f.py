"""3.7.24F: real journey/StoryBook sandbox behavior without file writes."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.world_map import default_world
from sporebound.world_travel_lab import (MAX_STEPS_PER_RUN, WorldTravelLab,
                                         campaign_delta)


class WorldTravelLabTests(TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.content.missions["garden"].next_missions.append("hold")
        self.project = GameProject.default(self.content)
        self.project.world = default_world(self.content, self.project.campaigns)
        self.project.story = {"scenes": [
            {"id": "caravan", "title": "Caravane", "speaker": "Marchand",
             "text": "Choisir une route.", "choices": [
                 {"id": "forward", "label": "Poursuivre",
                  "effects": [{"kind": "add_flag",
                               "flag": "merchant_trust", "amount": 1}]},
                 {"id": "fork", "label": "Vers les collines",
                  "effects": [{"kind": "unlock_mission",
                               "mission": "hold"}]},
                 {"id": "back", "label": "Retour au carrefour"},
             ]},
            {"id": "toll", "title": "Péage", "speaker": "Garde",
             "text": "Un péage.", "choices": [
                 {"id": "pass", "label": "Continuer",
                  "effects": [{"kind": "set_flag",
                               "flag": "toll_seen", "value": True}]},
                 {"id": "pay", "label": "Payer 5",
                  "when": {"gold_gte": 5},
                  "effects": [{"kind": "gold", "amount": -5}]},
             ]},
        ]}
        self.project.world["events"] = [
            {"id": "caravan", "from": "garden", "to": "escape", "step": 2,
             "scene": "caravan",
             "routes": {"fork": {"kind": "destination", "mission": "hold"},
                        "back": {"kind": "return"}}},
            {"id": "toll", "from": "garden", "to": "escape", "step": 6,
             "scene": "toll"},
        ]
        self.project.validate(self.content)
        self.content_before = deepcopy(self.content.to_dict())
        self.project_before = deepcopy(self.project.to_dict())

    def lab(self, **kwargs):
        return WorldTravelLab(
            self.content, self.project, "main", "garden", "escape", **kwargs)

    def test_two_events_and_effect_differences_without_mutating_project(self):
        lab = self.lab()
        state = lab.snapshot()
        self.assertEqual(state["mode"], "auteur")
        self.assertNotIn("hold", lab.progress.unlocked)
        self.assertEqual(state["world"]["route"], ["garden", "escape"])
        state = lab.run_to_stop()
        self.assertEqual(state["scene"]["id"], "caravan")
        self.assertEqual(state["world"]["step"], 2)
        with self.assertRaises(RuleError):
            lab.step()
        decision = lab.choose("forward")
        self.assertIn("Flag merchant_trust", "\n".join(decision["changes"]))
        state = lab.run_to_stop()
        self.assertEqual(state["scene"]["id"], "toll")
        self.assertEqual(state["world"]["step"], 6)
        self.assertEqual({x["id"] for x in state["choices"]}, {"pass"})
        lab.choose("pass")
        final = lab.run_to_stop()
        self.assertTrue(final["finished"])
        self.assertEqual(final["world"]["at"], "escape")
        self.assertIn("Flag toll_seen", "\n".join(final["changes"]))
        self.assertEqual(self.content.to_dict(), self.content_before)
        self.assertEqual(self.project.to_dict(), self.project_before)
        self.assertEqual(len(lab.progress.story_history), 2)
        replayed = GameSession.from_recording(
            lab.session.recording(), self.content, self.project)
        self.assertEqual(replayed.progress.story_flags, lab.progress.story_flags)

    def test_branch_choice_and_physical_return_are_visible(self):
        lab = self.lab()
        lab.run_to_stop()
        state = lab.choose("fork")
        self.assertIn("Mission débloquée : hold", state["changes"])
        self.assertEqual(state["world"]["goal"], "hold")
        self.assertTrue(state["world"]["reversing"])
        state = lab.step()
        self.assertEqual(state["world"]["step"], 1)
        state = lab.run_to_stop()
        self.assertTrue(state["finished"])
        self.assertEqual(state["world"]["at"], "hold")
        self.assertFalse(state["world"]["reversing"])
        self.assertIn("Retour au carrefour", "\n".join(state["log"]))
        self.assertFalse(any(line.startswith("Rencontre : Péage")
                             for line in state["log"]))

    def test_go_back_and_rechoose_route_without_refiring_event(self):
        lab = self.lab()
        lab.run_to_stop()
        lab.choose("back")
        state = lab.run_to_stop()
        self.assertTrue(state["finished"])
        self.assertEqual(state["world"]["at"], "garden")
        lab.destination("escape")
        state = lab.run_to_stop()
        self.assertEqual(state["scene"]["id"], "toll")
        lab.choose("pass")
        self.assertEqual(lab.run_to_stop()["world"]["at"], "escape")

    def test_strict_mode_respects_locked_destination(self):
        with self.assertRaises(RuleError):
            self.lab(author_mode=False)
        session = GameSession.new(self.content, self.project, "main")
        campaign = deepcopy(session.progress)
        campaign.unlocked.append("escape")
        lab = self.lab(author_mode=False, progress=campaign)
        lab.run_to_stop()
        self.assertEqual(lab.snapshot()["scene"]["id"], "caravan")
        self.assertEqual(campaign.story_flags, session.progress.story_flags)
        self.assertEqual(campaign.story_history, [])

    def test_unavailable_choice_and_step_budget_are_atomic(self):
        lab = self.lab()
        with self.assertRaises(RuleError):
            lab.run_to_stop(0)
        self.assertEqual(lab.run_to_stop(max_steps=1)["world"]["step"], 1)
        lab.run_to_stop()
        checkpoint = deepcopy(lab.session.recording())
        with self.assertRaises(RuleError):
            lab.choose("invalid_choice")
        self.assertEqual(lab.session.recording(), checkpoint)
        self.assertEqual(lab.run_to_stop()["scene"]["id"], "caravan")
        with self.assertRaises(RuleError):
            lab.destination("hold")
        self.assertEqual(lab.session.recording(), checkpoint)

    def test_intro_is_explicitly_skipped_only_for_synthetic_lab(self):
        project = deepcopy(self.project)
        project.story["entry_scenes"] = {"main": "caravan"}
        project.validate(self.content)
        lab = WorldTravelLab(
            self.content, project, "main", "garden", "escape")
        self.assertTrue(any("Introduction ignorée" in x for x in lab.log))
        original = GameSession.new(self.content, project, "main")
        self.assertEqual(original.active_scene()["id"], "caravan")
        with self.assertRaises(RuleError):
            WorldTravelLab(
                self.content, project, "main", "garden", "escape",
                progress=original.progress)

    def test_campaign_delta_is_noop_for_cursor_only_and_bounded(self):
        lab = self.lab()
        initial = deepcopy(lab.progress)
        lab.step()
        self.assertEqual(campaign_delta(initial, lab.progress), [])
        with self.assertRaises(RuleError):
            lab.run_to_stop(MAX_STEPS_PER_RUN + 1)
        self.assertEqual(self.project.to_dict(), self.project_before)
