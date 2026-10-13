"""3.7.21D: direct cinematics follow canonical tactical events, without replay mutation."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.cinematics import (
    cinematic_template, matching_cinematics, tactical_event_target,
    triggered_tactical_cinematics,
)
from sporebound.engine import Battle
from sporebound.event_context import inspect_event
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.player_app import PlayerApplication
from sporebound.rules import triggers


class TacticalCinematicBridgeTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.target = tactical_event_target("garden", "spore_pulse")
        self.first = cinematic_template(
            "spore_cut", "Spores au jardin", "tactical_event", self.target)
        self.second = cinematic_template(
            "spore_voice", "La menace", "tactical_event", self.target)

    def project_with_clips(self, *clips):
        raw = self.project.to_dict()
        raw["cinematics"] = list(deepcopy(clips))
        return GameProject.from_dict(raw, self.content)

    def test_save_reload_references_one_real_tactical_trigger(self):
        project = self.project_with_clips(self.first)
        self.assertEqual(
            matching_cinematics(project, "tactical_event", self.target),
            [self.first])
        self.assertEqual(project.cinematics[0]["trigger"],
                         {"kind": "tactical_event", "target": self.target})
        with TemporaryDirectory() as directory:
            path = Path(directory) / "test.game.json"
            project.save(path, self.content)
            restored = GameProject.load(path, self.content)
            self.assertEqual(restored.cinematics, [self.first])
        self.assertEqual(
            GameProject.from_dict(self.project.to_dict(), self.content)
            .cinematics, [])

    def test_references_to_unknown_events_or_missions_fail_before_save(self):
        original = deepcopy(self.project.to_dict())
        for target in ("garden/missing", "missing/spore_pulse",
                       "garden/", "crown/not_a_trigger"):
            with self.subTest(target=target), self.assertRaises(RuleError):
                clip = deepcopy(self.first)
                clip["trigger"]["target"] = target
                self.project_with_clips(clip)
        self.assertEqual(self.project.to_dict(), original)

    def test_engine_firing_controls_order_and_no_duplicate_playback(self):
        project = self.project_with_clips(self.first, self.second)
        battle = Battle(self.content, "garden", seed=7)
        observed = deepcopy(self.content.to_dict())
        initial_fired = set(battle.fired)
        clips, acknowledgements = triggered_tactical_cinematics(
            project, battle, initial_fired)
        self.assertEqual(clips, [])
        self.assertEqual(acknowledgements, initial_fired)
        battle.tick = 20
        triggers.dispatch(battle)
        self.assertIn("spore_pulse", battle.fired)
        clips, acknowledgements = triggered_tactical_cinematics(
            project, battle, initial_fired)
        self.assertEqual([item["id"] for item in clips],
                         ["spore_cut", "spore_voice"])
        clips[0]["name"] = "Modified presentation copy"
        self.assertEqual(project.cinematics[0]["name"], "Spores au jardin")
        again, updated = triggered_tactical_cinematics(
            project, battle, acknowledgements)
        self.assertEqual(again, [])
        self.assertEqual(updated, acknowledgements)
        # Reload/reopen initializes presentation cursor from the saved
        # authoritative fired set instead of silently replaying a cutscene.
        resumed, _ = triggered_tactical_cinematics(
            project, battle, battle.fired)
        self.assertEqual(resumed, [])
        self.assertEqual(self.content.to_dict(), observed)

    def test_context_marks_tactical_clip_as_direct_not_mission_scoped(self):
        clip = deepcopy(self.second)
        clip["trigger"] = {"kind": "after_mission", "target": "garden"}
        project = self.project_with_clips(self.first, clip)
        ctx = inspect_event(self.content.to_dict(), "garden",
                            "spore_pulse", project)
        self.assertEqual(ctx["links_scope"], "event-and-mission")
        self.assertEqual(ctx["cinematics"], [
            {"id": "spore_cut", "stage": "tactical_event", "scope": "event"},
            {"id": "spore_voice", "stage": "after_mission", "scope": "mission"},
        ])
        self.assertEqual(self.content.to_dict()["missions"][0]["triggers"][0]["id"],
                         "spore_pulse")


    def test_player_displays_once_and_seeds_seen_events_after_loading(self):
        project = self.project_with_clips(self.first, self.second)
        battle = Battle(self.content, "garden")
        ui = object.__new__(PlayerApplication)
        ui.project = project
        ui.player = SimpleNamespace(
            session=SimpleNamespace(active_battle=battle))
        ui._seen_tactical_cinematics = {}
        played, redraws = [], []
        ui._play_cinematic_clips = lambda clips, finish: played.append(
            [clip["id"] for clip in clips])
        ui.show = lambda: redraws.append("draw")
        ui._change(lambda: None)
        self.assertEqual(redraws, ["draw"])
        battle.tick = 20
        triggers.dispatch(battle)
        ui._change(lambda: None)
        self.assertEqual(played, [["spore_cut", "spore_voice"]])
        self.assertEqual(redraws, ["draw"])
        ui._change(lambda: None)
        self.assertEqual(len(played), 1)
        self.assertEqual(len(redraws), 2)
        ui._acknowledge_loaded_tactical_cinematics()
        ui._change(lambda: None)
        self.assertEqual(len(played), 1)
        self.assertEqual(len(redraws), 3)


if __name__ == "__main__":
    unittest.main()
