"""3.8.4 human-played encounters: opt-in only, truthful durations, local export."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from sporebound.playtest_telemetry import (PlaytestRecorder,
    analyze_playtests, save_playtest, validate_report)
from sporebound.player_controller import PlayerController
from sporebound.model import RuleError


@dataclass
class Unit:
    id: str
    hp: int
    team: str
    pos: tuple = (0, 0)

    @property
    def alive(self):
        return self.hp > 0


class Battle:
    def __init__(self):
        self.battle_id = "battle_one"
        self.mission = type("Mission", (), {
            "id": "garden", "objective": "hold", "goal": [(0, 0)]})()
        self.units = [Unit("hero", 40, "player"), Unit("foe", 30, "enemy", (2, 0))]
        self.active = self.units[0]
        self.tick = 10
        self.events = []
        self.commands = []
        self.hold_ticks = 0
        self.result = None


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, secs):
        self.value += secs


class RecorderTests(unittest.TestCase):
    def test_default_off_and_local_export_json_are_not_savegames(self):
        clock = Clock()
        rec = PlaytestRecorder(clock=clock)
        battle = Battle()
        before = rec.before(battle)
        rec.committed("execute", before, battle,
                      command={"kind": "act", "cell": [1, 0]})
        self.assertEqual(rec.report()["sessions"], [])
        rec.enable(battle)
        prior = rec.before(battle)
        clock.advance(80)
        battle.events.append({"kind": "damage", "source": "hero",
                              "unit": "foe", "amount": 7,
                              "cell": [2, 0], "private_string": "ignored"})
        battle.commands.append({"kind": "act", "cell": [2, 0]})
        battle.tick += 8
        rec.committed("execute", prior, battle,
                      command={"kind": "act", "skill": "attack",
                               "cell": [2, 0]})
        prior = rec.before(battle)
        clock.advance(100)
        battle.active = battle.units[1]
        battle.result = "victory"
        battle.tick += 12
        battle.commands.append({"kind": "end"})
        rec.committed("execute", prior, battle, command={"kind": "end"})
        report = rec.report()
        self.assertEqual(len(report["sessions"]), 1)
        session = report["sessions"][0]
        self.assertEqual(session["outcome"], "victory")
        self.assertEqual(session["duration_seconds"], 180)
        self.assertTrue(session["partial_capture"])
        self.assertEqual(session["damage_observed"], 7)
        self.assertEqual(session["command_kinds"], {"act": 1, "end": 1})
        self.assertEqual(session["events"][0]["command"],
                         {"kind": "act", "skill": "attack"})
        self.assertNotIn("private_string",
                         session["events"][0]["engine_events"][0])
        self.assertNotIn("cell",
                         session["events"][0]["engine_events"][0])
        self.assertNotIn("profile", json.dumps(report))
        with TemporaryDirectory() as root:
            path = Path(root) / "manual_playtest.json"
            save_playtest(path, report)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), report)

    def test_abandonment_and_real_human_minutes_only_complete_samples(self):
        clock = Clock()
        rec = PlaytestRecorder(clock=clock)
        battle = Battle()
        rec.enable()
        rec.committed("start_mission", None, battle)
        clock.advance(1200)
        previous = rec.before(battle)
        rec.committed("abandon_encounter", previous, None)
        self.assertEqual(rec.report()["sessions"][0]["outcome"], "abandoned")
        second = Battle()
        second.battle_id = "battle_two"
        rec.committed("start_mission", None, second)
        clock.advance(900)
        previous = rec.before(second)
        second.result = "victory"
        second.tick = 150
        rec.committed("execute", previous, second, command={"kind": "end"})
        summary = analyze_playtests(rec.report(), mission="garden")
        self.assertEqual(summary["sessions"], 2)
        self.assertEqual(summary["outcomes"], {"abandoned": 1, "victory": 1})
        self.assertEqual(summary["complete_observations"], 1)
        self.assertEqual(summary["abandonment_rate"], 0.5)
        self.assertEqual(summary["human_duration_minutes_p50"], 15.0)
        self.assertEqual(summary["human_duration_minutes_p95"], 15.0)
        self.assertEqual(summary["player_commands"], {"end": 1})
        summary = analyze_playtests(rec.report(), mission="garden",
            ai_report={"kind": "battle_lab", "mission": "garden",
                       "victory_rate": .4, "ticks_p95": 100,
                       "commands_p95": 90})
        self.assertEqual(summary["ai_reference"]["ct_p95"], 100)
        self.assertEqual(summary["human_duration_minutes_p50"], 15.0)
        with self.assertRaises(RuleError):
            analyze_playtests(rec.report(), mission="garden",
                              ai_report={"kind": "invalid", "mission": "garden"})

    def test_controller_records_only_after_persistence_success(self):
        clock = Clock()
        recorder = PlaytestRecorder(clock=clock)
        recorder.enable()
        battle = Battle()

        class Session:
            def __init__(self, b):
                self.active_battle = b

            def recording(self):
                return {"valid": True}

            def execute(self, command):
                battle.commands.append(command)
                battle.tick += 2
                battle.events.append({"kind": "damage", "amount": 2})
                return battle

        controller = object.__new__(PlayerController)
        controller.session = Session(battle)
        controller.playtest = recorder
        saved = []
        controller.save = lambda: saved.append(True)
        clock.advance(30)
        controller.execute({"kind": "act", "skill": "attack"})
        self.assertEqual(saved, [True])
        self.assertEqual(recorder.report()["sessions"][0]["events"][0]["seconds"], 0)
        self.assertEqual(recorder.report()["sessions"][0]["events"][0]["team"],
                         "player")
        self.assertEqual(len(battle.commands), 1)

    def test_stopped_and_partial_are_not_successful_human_completions(self):
        clock = Clock()
        rec = PlaytestRecorder(clock=clock)
        rec.enable(Battle())
        clock.advance(300)
        rec.disable()
        result = rec.report()
        self.assertEqual(result["sessions"][0]["outcome"], "stopped")
        summary = analyze_playtests(result)
        self.assertEqual(summary["complete_observations"], 0)
        self.assertIsNone(summary["human_duration_minutes_p50"])
        invalid = dict(result, opt_in=False)
        with self.assertRaises(RuleError):
            validate_report(invalid)


if __name__ == "__main__":
    unittest.main()
