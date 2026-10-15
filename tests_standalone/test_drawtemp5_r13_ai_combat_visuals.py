"""R13.8 graphical AI decisions and actual damage/heal event source tests."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import unittest

from drawtemp.sdk.r13_ai_combat_visuals import build_combat_visuals
from sporebound.battle_diagnostics import trace_seed
from sporebound.encounter_balance6 import ai_decision_analytics
from sporebound.model import Board, Content, Mission, RuleError, Unit


def arena():
    return Content({}, {"visual": Mission(
        "visual", "Combat Visuals", Board(6, 5), [
            Unit("hero", "Hero", "player", (0, 1)),
            Unit("enemy", "Enemy", "enemy", (4, 1)),
        ])})


class CombatTelemetryR13Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = arena()
        cls.trace = trace_seed(cls.content, "visual", seed=17, max_commands=64)

    def test_graph_data_exact_canonical_actions_events_no_mutation(self):
        original = deepcopy(self.trace)
        model = build_combat_visuals(self.trace)
        analytic = ai_decision_analytics(self.trace)
        self.assertEqual(model["kind"], "r13_ai_combat_visuals")
        self.assertEqual(model["steps"], len(self.trace["steps"]))
        self.assertEqual(len(model["curve"]), len(self.trace["steps"])+1)
        self.assertEqual(model["curve"][0]["step"], 0)
        self.assertEqual(model["action_totals"], analytic["actions"])
        self.assertEqual(sum(model["action_totals"].values()),
                         len(self.trace["steps"]))
        self.assertEqual(model["signals"], analytic["signals"])
        self.assertEqual(model["signal_evidence"], analytic["evidence"])
        self.assertEqual(json.loads(json.dumps(model)), model)
        self.assertEqual(self.trace, original)

        totals = {"player": Counter(), "enemy": Counter()}
        actual_events = []
        for index, step in enumerate(self.trace["steps"], 1):
            for event in step["events"]:
                if event["kind"] in {"damage", "heal"}:
                    actual_events.append((index, event))
        self.assertEqual(len(model["combat_events"]), len(actual_events))
        for source, (step, event) in zip(model["combat_events"], actual_events):
            self.assertEqual(source["step"], step)
            self.assertEqual(source["kind"], event["kind"])
            self.assertEqual(source["target"], event["unit"])
            self.assertEqual(source["amount"], event["amount"])
            totals[source["team"]][source["kind"]] += source["amount"]
        for team in ("player", "enemy"):
            self.assertEqual(
                model["team_damage_received"].get(team, 0),
                totals[team]["damage"])
            self.assertEqual(
                model["team_healing_received"].get(team, 0),
                totals[team]["heal"])
        self.assertEqual(model["curve"][-1]["damage_enemy"],
                         totals["enemy"]["damage"])

    def test_reject_unverified_ordering_negative_or_unknown_events(self):
        for key, value in (("kind", "other"),
                           ("replay_verified", False)):
            bad = deepcopy(self.trace)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(RuleError):
                build_combat_visuals(bad)
        bad = deepcopy(self.trace)
        bad["steps"][0]["index"] = 8
        with self.assertRaises(RuleError):
            build_combat_visuals(bad)
        for event in (
                {"kind": "damage", "unit": "missing", "amount": 2},
                {"kind": "heal", "unit": "hero", "amount": -1},
                {"kind": "damage", "unit": "hero", "amount": True}):
            bad = deepcopy(self.trace)
            bad["steps"][0]["events"].append(event)
            with self.subTest(event=event), self.assertRaises(RuleError):
                build_combat_visuals(bad)
        bad = deepcopy(self.trace)
        bad["steps"] *= 81  # Exceeds configured 5000-step hard cap.
        with self.assertRaises(RuleError):
            build_combat_visuals(bad)

    def test_zero_steps_explicit_and_canonical_analytics(self):
        base = deepcopy(self.trace)
        base["steps"] = []
        # This particular empty-but-verified fixture is only for checking
        # view state. It is NOT a claim of an independently verified replay.
        result = build_combat_visuals(base)
        self.assertEqual(result["steps"], 0)
        self.assertEqual(result["curve"][0]["step"], 0)
        self.assertEqual(result["combat_events"], [])
        self.assertEqual(result["action_totals"], {})


if __name__ == "__main__":
    unittest.main()
