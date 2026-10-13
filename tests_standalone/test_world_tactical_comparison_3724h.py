"""3.7.24H: tactical telemetry follows each route's actual Campaign state."""
from copy import deepcopy
from unittest import TestCase

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.battle_lab import compare_reports, run_lab
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.world_map import default_world
from sporebound.world_route_comparison import WorldRouteComparison
from sporebound.world_tactical_comparison import (
    contextual_battle_comparison, tactical_rows)
from sporebound.world_travel_lab import WorldTravelLab


class RouteTacticalComparisonTests(TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.project.world = default_world(self.content, self.project.campaigns)
        self.project.story = {"scenes": [{
            "id": "escort", "title": "Escorte", "speaker": "Marchande",
            "text": "Accepter la mission ?", "choices": [
                {"id": "accept", "label": "Aider",
                 "effects": [{"kind": "set_flag",
                              "flag": "road_escort", "value": 1}]},
                {"id": "refuse", "label": "Refuser"},
                {"id": "return", "label": "Faire demi-tour"},
            ]}]}
        self.project.world["events"] = [{
            "id": "caravan", "from": "garden", "to": "escape",
            "step": 2, "scene": "escort",
            "routes": {"return": {"kind": "return"}},
        }]
        self.project.battle_support = [{
            "mission": "escape", "flag": "road_escort",
            "gte": 1, "potion_bonus": 2,
        }]
        self.project.validate(self.content)
        self.original_content = deepcopy(self.content.to_dict())
        self.original_project = deepcopy(self.project.to_dict())
        lab = WorldTravelLab(self.content, self.project,
                             "main", "garden", "escape")
        lab.run_to_stop()
        self.compare = WorldRouteComparison(lab)
        outcome = self.compare.compare_choices()
        self.assertEqual(len(outcome["added"]), 3)

    def test_real_campaign_support_is_reflected_in_battle_lab(self):
        report = contextual_battle_comparison(
            self.compare, "escape", seeds=(2,), max_commands=12)
        self.assertEqual(report["reference"], "1. Aider")
        self.assertEqual(report["mission"], "escape")
        self.assertEqual(report["seeds"], [2])
        yes = report["variants"]["1. Aider"]
        no = report["variants"]["2. Refuser"]
        back = report["variants"]["3. Faire demi-tour"]
        self.assertEqual(yes["status"], "measured")
        self.assertEqual(no["status"], "measured")
        self.assertEqual(back["status"], "unavailable")
        self.assertTrue(all(
            row["replay_verified"] for row in (yes, no)))
        self.assertEqual(yes["support_potions"], 5)
        self.assertEqual(no["support_potions"], 3)
        self.assertNotEqual(yes["setup_sha256"], no["setup_sha256"])
        self.assertTrue(no["vs_reference"]["authored_inputs_changed"])
        self.assertEqual(yes["report"]["samples"][0]["initial_inventory"]["potion"], 5)
        self.assertEqual(no["report"]["samples"][0]["initial_inventory"]["potion"], 3)
        self.assertEqual(self.content.to_dict(), self.original_content)
        self.assertEqual(self.project.to_dict(), self.original_project)
        rows = tactical_rows(report)
        self.assertEqual(rows["names"],
                         ["1. Aider", "2. Refuser", "3. Faire demi-tour"])
        self.assertTrue(any(
            row["metric"] == "Potions au départ"
            and row["values"] == ["5", "3", "—"]
            for row in rows["rows"]))

    def test_repeatability_same_seed_and_context_and_no_mutation(self):
        first = contextual_battle_comparison(
            self.compare, "escape", seeds=(3,), max_commands=9)
        second = contextual_battle_comparison(
            self.compare, "escape", seeds=(3,), max_commands=9)
        self.assertEqual(first, second)
        self.assertEqual(self.content.to_dict(), self.original_content)
        self.assertEqual(self.project.to_dict(), self.original_project)
        self.assertEqual(self.compare.checkpoint.snapshot()["scene"]["id"],
                         "escort")

    def test_locked_and_unarrived_missions_not_executed(self):
        report = contextual_battle_comparison(
            self.compare, "hold", seeds=(4,), max_commands=8)
        self.assertTrue(all(
            item["status"] == "unavailable"
            for item in report["variants"].values()))
        self.assertEqual(report["reference"], "")
        self.assertTrue(any(
            "verrouillée" in item["reason"] or "groupe" in item["reason"]
            for item in report["variants"].values()))
        self.assertEqual(self.project.to_dict(), self.original_project)

    def test_new_context_flag_prevents_false_determinism_drift(self):
        content = self.content
        progress = self.compare.variants["1. Aider"].progress
        support = self.compare.variants["1. Aider"].session._battle_support("escape")
        after = run_lab(content, "escape", seeds=(5,), max_commands=8,
                        progress=progress, initial_state=support)
        again = run_lab(content, "escape", seeds=(5,), max_commands=8,
                        progress=progress, initial_state=support)
        self.assertEqual(after, again)
        self.assertTrue(compare_reports(after, again)["passed"])
        other = self.compare.variants["2. Refuser"].progress
        plain = run_lab(content, "escape", seeds=(5,), max_commands=8,
                        progress=other)
        comparison = compare_reports(after, plain)
        self.assertTrue(comparison["authored_inputs_changed"])

    def test_invalid_limits_and_missing_variants(self):
        for kwargs in ({"seeds": ()}, {"seeds": (1, 1)},
                       {"seeds": (1,)*21}, {"max_commands": 0},
                       {"max_commands": 2001}):
            with self.subTest(kwargs=kwargs), self.assertRaises(RuleError):
                contextual_battle_comparison(self.compare, "escape", **kwargs)
        with self.assertRaises(RuleError):
            contextual_battle_comparison(self.compare, "not_mission")
