"""R25.A headless gates: profiles, Jeanne compatibility, fixed-step replay."""
from copy import deepcopy
import json
import unittest

from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.fixed_clock import FixedTickJournal, _digest
from sporebound.game_modes import PRESETS, legacy_modes, resolve_scene_profile
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import RuleError


class ModeProfileTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()

    def test_legacy_project_json_and_checkpoint_remain_identical(self):
        original = self.project.to_dict()
        original_recording = GameSession.new(
            self.content, self.project, "main", seed=31).recording()
        self.assertNotIn("game_modes", original)
        self.assertEqual(self.project.game_modes, {})
        self.assertEqual(resolve_scene_profile({}), PRESETS["srpg"])
        self.assertEqual(legacy_modes()["default"], {"preset": "srpg"})
        migrated = GameProject.from_dict(original, self.content)
        self.assertEqual(migrated.to_dict(), original)
        self.assertEqual(GameSession.new(
            self.content, migrated, "main", seed=31).recording(),
            original_recording)

    def test_profiles_are_saved_in_canonical_game_project(self):
        self.project.game_modes = {
            "version": 1, "default": {"preset": "srpg"},
            "scenes": {"arrival": {"preset": "narrative"},
                       MISSION: {"preset": "srpg"}},
        }
        self.project.validate(self.content)
        encoded = self.project.to_dict()
        restored = GameProject.from_dict(
            json.loads(json.dumps(encoded)), self.content)
        self.assertEqual(restored.to_dict(), encoded)
        session = GameSession.new(self.content, restored, "main")
        self.assertEqual(session.scene_profile()["combat"], "TACTICAL_CT")
        self.assertEqual(session.scene_profile("arrival")["combat"], "NONE")
        self.assertEqual(session.scene_profile(MISSION)["combat"], "TACTICAL_CT")
        detached = session.scene_profile("arrival")
        detached["combat"] = "ACTION_REALTIME"
        self.assertEqual(session.scene_profile("arrival")["combat"], "NONE")
        # Tactical startup and legacy session replay must still function.
        session.choose_story_option("enter")
        self.assertIsNotNone(session.start_mission(MISSION))
        replay = GameSession.from_recording(
            session.recording(), self.content, restored)
        self.assertEqual(replay.recording(), session.recording())

    def test_hybrid_project_requires_explicit_ct_scene_override(self):
        self.project.game_modes = {
            "version": 1, "default": {"preset": "hybrid"},
            "scenes": {MISSION: {"preset": "srpg"}},
        }
        self.project.validate(self.content)
        self.assertEqual(GameSession.new(
            self.content, self.project, "main").scene_profile(MISSION),
            PRESETS["srpg"])
        self.project.game_modes["scenes"].clear()
        with self.assertRaises(RuleError):
            self.project.validate(self.content)

    def test_invalid_or_future_profiles_fail_closed(self):
        good = {"version": 1, "default": {"preset": "srpg"}, "scenes": {}}
        invalid = [
            {"version": 2, "default": {"preset": "srpg"}, "scenes": {}},
            {"version": True, "default": {"preset": "srpg"}, "scenes": {}},
            {"version": 1, "default": {"preset": "unknown"}, "scenes": {}},
            {"version": 1, "default": {"preset": "srpg"},
             "scenes": {"missing_scene": {"preset": "narrative"}}},
            {"version": 1, "default": {"preset": "srpg"},
             "scenes": {MISSION: {"preset": "action"}}},
            {"version": 1, "default": {"preset": "srpg"}, "scenes": {},
             "unknown": 1},
            {"version": 1, "default": {"profile": {
                **PRESETS["srpg"], "movement": "FREE_REALTIME",
            }}, "scenes": {}},
            {"version": 1, "default": {"profile": {
                **PRESETS["action"], "camera": "ISOMETRIC",
            }}, "scenes": {}},
        ]
        for data in invalid:
            with self.subTest(data=data):
                self.project.game_modes = deepcopy(data)
                with self.assertRaises(RuleError):
                    self.project.validate(self.content)
        self.project.game_modes = good
        self.project.validate(self.content)

    def test_unknown_new_project_keys_do_not_silently_migrate(self):
        data = self.project.to_dict()
        data["game_modes"] = {"version": 999, "default": {"preset": "srpg"},
                              "scenes": {}}
        with self.assertRaises(RuleError):
            GameProject.from_dict(data, self.content)


class FixedClockTests(unittest.TestCase):
    @staticmethod
    def make_handler():
        state = {"positions": {}, "ticks": 0}

        def apply(tick, commands):
            state["ticks"] = tick
            for row in commands:
                name = row["source"]
                state["positions"][name] = (
                    state["positions"].get(name, 0)
                    + row["command"].get("distance", 0))
            return deepcopy(state)

        return apply

    def test_fixed_ticks_order_json_checkpoint_and_replay(self):
        journal = FixedTickJournal(rate=60, seed=42)
        journal.submit(2, "hero", {"kind": "move", "distance": 2})
        journal.submit(1, "zeta", {"kind": "move", "distance": 4})
        journal.submit(1, "alpha", {"kind": "move", "distance": 1})
        live = self.make_handler()
        first = journal.step(live)
        self.assertEqual(first["positions"], {"alpha": 1, "zeta": 4})
        self.assertEqual(journal.tick, 1)
        second = journal.step(live)
        self.assertEqual(second["positions"]["hero"], 2)
        record = json.loads(json.dumps(journal.recording()))
        self.assertEqual([row["source"] for row in record["inputs"]],
                         ["alpha", "zeta", "hero"])
        restored = FixedTickJournal.replay(record, self.make_handler())
        self.assertEqual(restored.recording(), record)

    def test_replay_detects_tampered_checksum_and_divergent_rules(self):
        journal = FixedTickJournal()
        journal.submit(1, "hero", {"kind": "move", "distance": 1})
        journal.step(self.make_handler())
        authentic = journal.recording()
        broken = deepcopy(authentic)
        broken["inputs"][0]["command"]["distance"] = 99
        with self.assertRaises(RuleError):
            FixedTickJournal.replay(broken, self.make_handler())
        # Even if an attacker re-hashes a structurally valid file, the
        # per-tick state checksum detects a replay with different rules.
        with self.assertRaises(RuleError):
            FixedTickJournal.replay(authentic, lambda tick, rows: {"wrong": True})
        broken = deepcopy(authentic)
        broken["states"][0] = "0" * 64
        broken["digest"] = _digest({k: v for k, v in broken.items()
                                    if k != "digest"})
        with self.assertRaises(RuleError):
            FixedTickJournal.replay(broken, self.make_handler())

    def test_rejected_input_and_failed_tick_do_not_commit(self):
        journal = FixedTickJournal()
        for tick, source, command in [
            (0, "hero", {"kind": "move"}),
            (True, "hero", {"kind": "move"}),
            (1, "", {"kind": "move"}),
            (1, "hero", {"speed": 2}),
            (1, "hero", {"kind": "move", "bad": float("nan")}),
        ]:
            with self.subTest(tick=tick, source=source, command=command):
                with self.assertRaises((ValueError, RuleError)):
                    journal.submit(tick, source, command)
        journal.submit(1, "hero", {"kind": "move", "distance": 3})
        with self.assertRaises(RuleError):
            journal.recording()
        def fail(_tick, _inputs):
            raise RuntimeError("external transaction failed")
        with self.assertRaises(RuntimeError):
            journal.step(fail)
        self.assertEqual(journal.tick, 0)
        state = journal.step(self.make_handler())
        self.assertEqual(state["positions"]["hero"], 3)
        self.assertEqual(journal.recording()["tick"], 1)


if __name__ == "__main__":
    unittest.main()
