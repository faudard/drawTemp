"""3.8 Battle Lab: real Battle runs, telemetry, paired reports and guards."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.battle_lab import compare_reports, run_lab, save_report
from sporebound.engine import Battle
from sporebound.model import Board, Content, Mission, RuleError, Unit


def arena():
    units = [
        Unit("hero", "Hero", "player", (0, 1), tags=["class:knight"]),
        Unit("healer", "Healer", "player", (0, 2), tags=["class:cleric"]),
        Unit("foe", "Enemy", "enemy", (4, 1), tags=["class:archer"], weapon="ranged"),
    ]
    return Content({}, {"lab": Mission("lab", "Laboratory", Board(7, 5), units)})


class BattleLabTests(unittest.TestCase):
    def test_measurements_replay_and_inputs_are_stable(self):
        content = arena()
        original = content.to_dict()
        rules_result = run_lab(content, "lab", seeds=(2, 7), max_commands=35)
        repeated = run_lab(content, "lab", seeds=(2, 7), max_commands=35)
        self.assertEqual(rules_result, repeated)
        self.assertEqual(content.to_dict(), original)
        self.assertEqual(rules_result["runs"], 2)
        self.assertEqual(rules_result["seeds"], [2, 7])
        self.assertEqual(rules_result["schema"], 1)
        self.assertEqual(rules_result["activations_ct"],
                         sum(row["activations_ct"] for row in rules_result["samples"]))
        self.assertEqual(rules_result["commands_p95"],
                         max(row["commands"] for row in rules_result["samples"]))
        self.assertTrue(all(row["replay_verified"]
                            for row in rules_result["samples"]))
        self.assertIn("player/knight", rules_result["class_survival"])
        self.assertIn("enemy/archer", rules_result["class_survival"])
        self.assertIn("damage", rules_result["samples"][0])
        self.assertIn("healing_received", rules_result["samples"][0])
        self.assertIn("reactions", rules_result["samples"][0])
        self.assertIn("decisions", rules_result["samples"][0])
        self.assertIn("objective", rules_result["samples"][0])
        self.assertTrue(any(s["decisions"] for s in rules_result["samples"]))

    def test_paired_comparison_detects_major_regressions(self):
        reference = run_lab(arena(), "lab", seeds=(3, 9), max_commands=22)
        current = deepcopy(reference)
        self.assertTrue(compare_reports(reference, current)["passed"])
        current["victory_rate"] = max(0, reference["victory_rate"] - 1)
        current["commands_p95"] += 30
        current["ticks_p95"] += 100
        current["outcomes"]["limit"] += 1
        current["samples"][0]["digest"] = "changed"
        delta = compare_reports(reference, current, max_victory_drop=0,
                                max_p95_growth=0, max_new_limits=0)
        self.assertFalse(delta["passed"])
        self.assertEqual(delta["status"], "fail")
        self.assertTrue(any("Determinism" in issue for issue in delta["issues"]))
        self.assertTrue(any("unresolved" in issue for issue in delta["issues"]))
        self.assertTrue(any("commands_p95" in issue for issue in delta["issues"]))
        modified_content = deepcopy(current)
        modified_content["content_sha256"] = "different authored version"
        self.assertFalse(any("Determinism" in item for item in
                             compare_reports(reference, modified_content,
                                             max_victory_drop=0,
                                             max_p95_growth=0)["issues"]))
        modified_content["seeds"] = [999, 9]
        with self.assertRaises(RuleError):
            compare_reports(reference, modified_content)

    def test_json_roundtrip_and_invalid_input(self):
        content = arena()
        report = run_lab(content, "lab", seeds=[0, 42], max_commands=15)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "baseline.json"
            save_report(path, report)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(compare_reports(loaded, report)["passed"])
        for kwargs in (
            {"seeds": [1, 1]}, {"seeds": []}, {"seeds": [-1]},
            {"seeds": [2**32]}, {"max_commands": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(RuleError):
                run_lab(content, "lab", **kwargs)
        with self.assertRaises(RuleError):
            run_lab(content, "missing", seeds=[1])

    def test_canonical_simulator_observer_does_not_change_digest(self):
        from sporebound.ai import simulate
        untouched = Battle(arena(), "lab", seed=8)
        observed = Battle(arena(), "lab", seed=8)
        events = []
        result = simulate(observed, 24, observer=lambda battle, cmd: events.append(
            (battle.active.id if battle.active else "", cmd["kind"])))
        original = simulate(untouched, 24)
        self.assertEqual(result, original)
        self.assertEqual(observed.recording()["commands"],
                         untouched.recording()["commands"])
        self.assertEqual(len(events), len(observed.commands))


if __name__ == "__main__":
    unittest.main()
