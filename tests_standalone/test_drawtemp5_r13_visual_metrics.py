"""R13.8: paired visual metrics are measured, verified and non-destructive."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from drawtemp.sdk.r13_visual_metrics import build_visual_comparison
from sporebound.battle_lab import run_lab
from sporebound.model import Board, Content, Mission, RuleError, Unit


def arena():
    return Content({}, {"lab": Mission(
        "lab", "Lab", Board(6, 5),
        [Unit("hero", "Hero", "player", (0, 1)),
         Unit("enemy", "Enemy", "enemy", (4, 1))],
    )})


class VisualBattleLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = arena()
        cls.baseline = run_lab(cls.content, "lab", seeds=(17, 3),
                               max_commands=20)
        cls.candidate = run_lab(cls.content, "lab", seeds=(17, 3),
                                max_commands=20)

    def test_single_visualization_uses_real_canonical_numbers(self):
        original = deepcopy(self.baseline)
        plot = build_visual_comparison(self.baseline)
        self.assertEqual(plot["kind"], "r13_visual_metrics")
        self.assertEqual(plot["mode"], "single")
        self.assertIsNone(plot["comparison"])
        self.assertEqual(plot["seed_order"], [17, 3])
        self.assertEqual(plot["series"][0]["aggregate"]["victory_percent"],
                         round(self.baseline["victory_rate"] * 100, 2))
        self.assertEqual(plot["series"][0]["aggregate"]["ticks_p95"],
                         self.baseline["ticks_p95"])
        self.assertEqual(plot["series"][0]["aggregate"]["commands_p95"],
                         self.baseline["commands_p95"])
        self.assertEqual(plot["series"][0]["aggregate"]["activations_per_run"],
                         round(self.baseline["activations_ct"] / 2, 2))
        self.assertEqual(plot["series"][0]["samples"][1]["result"],
                         self.baseline["samples"][1]["result"])
        self.assertEqual(plot["series"][0]["samples"][0]["commands"],
                         self.baseline["samples"][0]["commands"])
        self.assertIn("pas une durée humaine", plot["units_note"])
        self.assertEqual(json.loads(json.dumps(plot)), plot)
        self.assertEqual(self.baseline, original)

    def test_paired_visualization_preserves_seeds_and_true_deltas(self):
        baseline, candidate = deepcopy(self.baseline), deepcopy(self.candidate)
        plot = build_visual_comparison(baseline, candidate)
        self.assertEqual(plot["mode"], "comparison")
        self.assertEqual(plot["seed_order"], [17, 3])
        self.assertEqual(len(plot["series"]), 2)
        self.assertTrue(plot["comparison"]["passed"])
        self.assertEqual(plot["series"][0]["samples"][0]["seed"], 17)
        self.assertEqual(plot["series"][1]["samples"][1]["seed"], 3)
        self.assertEqual(plot["deltas"]["ticks_p95"], 0)
        self.assertEqual(plot["deltas"]["commands_p95"], 0)
        self.assertEqual(plot["deltas"]["victory_percent"], 0)
        self.assertEqual(baseline, self.baseline)
        self.assertEqual(candidate, self.candidate)

    def test_changed_objectives_require_human_review_not_pass(self):
        result = build_visual_comparison(
            self.baseline, self.candidate, objective_changed=True)
        self.assertFalse(result["comparison"]["passed"])
        self.assertTrue(result["comparison"]["objective_changed"])
        self.assertTrue(result["comparison"]["human_signoff_required"])
        self.assertTrue(result["comparison"]["issues"])

    def test_incompatible_seed_and_cap_are_rejected(self):
        for field, value in (("seeds", [3, 17]), ("max_commands", 19),
                             ("mission", "other")):
            wrong = deepcopy(self.candidate)
            wrong[field] = value
            with self.subTest(field=field), self.assertRaises(RuleError):
                build_visual_comparison(self.baseline, wrong)

    def test_tampering_with_replays_and_metrics_is_rejected(self):
        mutations = (
            lambda r: r["samples"][0].update(replay_verified=False),
            lambda r: r["samples"][0].update(ticks=float("nan")),
            lambda r: r["samples"][0].update(seed=42),
            lambda r: r["samples"][0].update(commands=-1),
            lambda r: r.update(runs=0),
            lambda r: r["outcomes"].update(victory=999),
            lambda r: r.update(victory_rate=float("nan")),
            lambda r: r.update(seeds=[17, 17]),
        )
        for mutate in mutations:
            invalid = deepcopy(self.baseline)
            mutate(invalid)
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                with self.assertRaises(RuleError):
                    build_visual_comparison(invalid)


if __name__ == "__main__":
    unittest.main()
