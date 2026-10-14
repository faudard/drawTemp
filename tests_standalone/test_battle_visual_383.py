"""3.8.3 visual telemetry: real reports, paired seeds and exact CT traces."""
from copy import deepcopy
import unittest

from sporebound.balance_matrix import run_matrix
from sporebound.battle_lab import run_lab
from sporebound.battle_diagnostics import trace_seed
from sporebound.battle_visual import (METRICS, chart_model,
                                     notable_seeds, timeline_model)
from sporebound.model import Board, Content, Mission, RuleError, Unit


def arena():
    units = [
        Unit("hero", "Hero", "player", (0, 1), tags=["class:knight"]),
        Unit("healer", "Healer", "player", (0, 2), tags=["class:cleric"]),
        Unit("foe", "Enemy", "enemy", (4, 1),
             tags=["class:archer"], weapon="ranged"),
    ]
    return Content({}, {
        "lab": Mission("lab", "Laboratory", Board(7, 5), units),
        "other": Mission("other", "Other", Board(7, 5),
                         deepcopy(units)),
    })


class VisualBattleLabTests(unittest.TestCase):
    def test_chart_model_is_deterministic_and_does_not_modify_source(self):
        content = arena()
        report = run_lab(content, "lab", seeds=[1, 7, 42], max_commands=30)
        source = deepcopy(report)
        model = chart_model(report)
        self.assertEqual(report, source)
        self.assertEqual(model, chart_model(report))
        self.assertEqual(model["seeds"], [1, 7, 42])
        self.assertEqual(model["units"]["ct"], "ticks CT")
        self.assertEqual(model["reference_win_rate"], None)
        self.assertEqual(sum(x["count"] for x in model["outcomes"]), 3)
        self.assertEqual(set(model["metrics"]), set(METRICS))
        self.assertTrue(all(x["replay_verified"] for x in model["samples"]))
        self.assertEqual(model["metrics"]["class_survival"][0]["name"],
                         sorted(report["class_survival"])[0])
        self.assertEqual(model["samples"][1]["ct"],
                         report["samples"][1]["ticks"])

    def test_paired_report_has_exact_per_seed_deltas_not_mixed_means(self):
        baseline = run_lab(arena(), "lab", seeds=[9, 3],
                           max_commands=20)
        newer = deepcopy(baseline)
        newer["samples"][0]["ticks"] += 4
        newer["samples"][0]["commands"] += 2
        newer["samples"][0]["result"] = "defeat"
        newer["samples"][1]["commands"] += 7
        newer["damage"]["dealt:enemy"] = (
            newer["damage"].get("dealt:enemy", 0) + 5)
        visual = chart_model(newer, reference=baseline)
        self.assertTrue(visual["paired"])
        self.assertEqual(visual["samples"][0]["ct_delta"], 4)
        self.assertEqual(visual["samples"][0]["commands_delta"], 2)
        self.assertEqual(visual["samples"][1]["commands_delta"], 7)
        self.assertIn(visual["samples"][0]["outcome_changed"],
                      (True, False))
        damage = next(row for row in visual["metrics"]["damage"]
                      if row["name"] == "dealt:enemy")
        self.assertEqual(damage["delta"], 5)
        reasons = notable_seeds(newer, reference=baseline)
        self.assertTrue(any("command_growth" in x["issues"] for x in reasons))
        mismatch = deepcopy(baseline)
        mismatch["mission"] = "other"
        with self.assertRaises(RuleError):
            chart_model(newer, reference=mismatch)
        mismatch = deepcopy(baseline)
        mismatch["seeds"].reverse()
        with self.assertRaises(RuleError):
            chart_model(newer, reference=mismatch)

    def test_matrix_variants_share_real_telemetry_and_mission_baseline(self):
        matrix = run_matrix(arena(), [
            {"id": "lab/armor", "mission": "lab",
             "team_deltas": {"enemy": {"defense": 1}}},
            {"id": "other/hp", "mission": "other",
             "team_deltas": {"player": {"max_hp": 5}}},
        ], seeds=(2, 8), max_commands=24)
        rows = {row["id"]: row for row in matrix["cases"]}
        for key in ("lab/armor", "other/hp"):
            row = rows[key]
            ref = rows[row["reference"]]
            visual = chart_model(row["report"], reference=ref["report"])
            self.assertEqual([x["seed"] for x in visual["samples"]], [2, 8])
            self.assertEqual(visual["mission"], row["mission"])
            self.assertEqual(visual["win_rate"] - visual["reference_win_rate"],
                             row["victory_delta"])

    def test_real_trace_points_and_findings_preserve_steps(self):
        report = run_lab(arena(), "lab", seeds=[5], max_commands=26)
        trace = trace_seed(arena(), "lab", seed=5, max_commands=26)
        model = timeline_model(trace, max_points=9)
        self.assertEqual(trace["digest"], report["samples"][0]["digest"])
        self.assertTrue(model["verified"])
        self.assertEqual(model["commands"], trace["commands"])
        self.assertEqual(model["final_tick"], trace["ticks"])
        self.assertLessEqual(len(model["points"]), 9)
        self.assertEqual(model["points"][-1]["step"], trace["commands"])
        self.assertTrue(all(item["step"] in [x["index"] for x in trace["steps"]]
                            for item in model["points"]))
        self.assertEqual(model, timeline_model(trace, max_points=9))
        with self.assertRaises(RuleError):
            timeline_model({**trace, "replay_verified": False})
        with self.assertRaises(RuleError):
            timeline_model(trace, max_points=1)

    def test_visible_alarms_do_not_fabricate_stalls(self):
        baseline = run_lab(arena(), "lab", seeds=[11, 4],
                           max_commands=10)
        changed = deepcopy(baseline)
        changed["samples"][0]["result"] = "limit"
        changed["samples"][0]["possible_stall"] = True
        changed["samples"][0]["commands"] += 3
        flagged = notable_seeds(changed, reference=baseline)
        self.assertEqual(flagged[0]["seed"], 11)
        self.assertIn("unresolved", flagged[0]["issues"])
        self.assertIn("possible_stall", flagged[0]["issues"])
        self.assertTrue(all("possible_stall" not in row["issues"]
                            for row in flagged if row["seed"] == 4))


if __name__ == "__main__":
    unittest.main()
