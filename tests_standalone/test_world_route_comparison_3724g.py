"""3.7.24G: compare several checkpoint-identical journeys via real StoryBook."""
from copy import deepcopy
from unittest import TestCase

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.world_map import default_world
from sporebound.world_route_comparison import (
    MAX_COMPARISON_PATHS, WorldRouteComparison)
from sporebound.world_travel_lab import WorldTravelLab


class RouteComparisonTests(TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.content.missions["garden"].next_missions.append("hold")
        self.project = GameProject.default(self.content)
        self.project.world = default_world(self.content, self.project.campaigns)
        self.project.story = {"scenes": [
            {"id": "caravan", "title": "Caravane", "speaker": "Marchande",
             "text": "Où aller ?", "choices": [
                 {"id": "forward", "label": "Aider et continuer",
                  "effects": [{"kind": "set_flag", "flag": "helped", "value": True}]},
                 {"id": "back", "label": "Revenir au village"},
                 {"id": "north", "label": "Rejoindre les collines",
                  "effects": [{"kind": "unlock_mission", "mission": "hold"}]},
             ]},
            {"id": "toll", "title": "Péage", "speaker": "Garde",
             "text": "Payez.", "choices": [
                 {"id": "pass", "label": "Passer",
                  "effects": [{"kind": "add_flag", "flag": "toll_pass", "amount": 1}]},
             ]},
        ]}
        self.project.world["events"] = [
            {"id": "caravan", "from": "garden", "to": "escape",
             "step": 2, "scene": "caravan",
             "routes": {
                 "back": {"kind": "return"},
                 "north": {"kind": "destination", "mission": "hold"}}},
            {"id": "toll", "from": "garden", "to": "escape",
             "step": 6, "scene": "toll"},
        ]
        self.project.validate(self.content)
        self.initial_project = deepcopy(self.project.to_dict())
        self.initial_content = deepcopy(self.content.to_dict())
        self.lab = WorldTravelLab(
            self.content, self.project, "main", "garden", "escape")
        self.lab.run_to_stop()
        self.assertEqual(self.lab.snapshot()["scene"]["id"], "caravan")

    def test_auto_compare_three_distinct_choices_and_matrix(self):
        original_checkpoint = self.lab.session.recording()
        compare = WorldRouteComparison(self.lab)
        result = compare.compare_choices()
        self.assertEqual(len(result["added"]), 3)
        self.assertEqual(result["failures"], [])
        matrix = result["matrix"]
        self.assertEqual(matrix["scene"], "caravan")
        self.assertEqual(len(matrix["names"]), 3)
        self.assertEqual(self.lab.session.recording(), original_checkpoint)
        outcomes = [compare.detail(name) for name in matrix["names"]]
        self.assertEqual(
            [row["state"]["at"] for row in outcomes],
            ["garden", "garden", "hold"])
        self.assertEqual(
            [row["state"]["goal"] for row in outcomes],
            ["escape", "", ""])
        self.assertEqual(
            [row["state"]["reversing"] for row in outcomes],
            [False, False, False])
        self.assertTrue(any("helped" in x for x in outcomes[0]["changes"]))
        self.assertIn("Mission débloquée : hold", outcomes[2]["changes"])
        self.assertTrue(any(
            row["metric"] == "Accessible : hold" and
            row["values"] == ["non", "non", "oui"]
            for row in matrix["rows"]))
        self.assertEqual(self.project.to_dict(), self.initial_project)
        self.assertEqual(self.content.to_dict(), self.initial_content)

    def test_manual_full_journeys_same_checkpoint_and_immutable_snapshots(self):
        compare = WorldRouteComparison(self.lab)
        branch_a = compare.fork()
        branch_a.choose("forward")
        branch_a.run_to_stop()
        branch_a.choose("pass")
        branch_a.run_to_stop()
        self.assertTrue(branch_a.snapshot()["finished"])
        compare.record("Protéger les marchands", branch_a)
        before = deepcopy(compare.detail("Protéger les marchands"))
        branch_a.destination("garden")
        branch_a.run_to_stop()
        self.assertEqual(compare.detail("Protéger les marchands"), before)
        branch_b = compare.fork()
        branch_b.choose("north")
        branch_b.run_to_stop()
        self.assertEqual(branch_b.snapshot()["world"]["at"], "hold")
        compare.record("Prendre la colline", branch_b)
        self.assertEqual(compare.matrix()["names"],
                         ["Protéger les marchands", "Prendre la colline"])
        matrix = compare.matrix()
        self.assertTrue(any(row["metric"] == "Lieu" and
                            row["values"] == ["escape", "hold"]
                            for row in matrix["rows"]))
        checkout = compare.checkout("Prendre la colline")
        checkout.destination("garden")
        checkout.run_to_stop()
        self.assertEqual(compare.detail("Prendre la colline")["state"]["at"], "hold")

    def test_wrong_provenance_duplicate_and_max_variants_rejected(self):
        compare = WorldRouteComparison(self.lab)
        with self.assertRaises(RuleError):
            compare.record("Étranger", self.lab)
        first = compare.fork()
        first.choose("back")
        first.run_to_stop()
        compare.record("Retour", first)
        with self.assertRaises(RuleError):
            compare.record("Retour", first)
        with self.assertRaises(RuleError):
            compare.checkout("Introuvable")
        for index in range(1, MAX_COMPARISON_PATHS):
            compare.record("Parcours " + str(index), first)
        self.assertEqual(len(compare.variants), MAX_COMPARISON_PATHS)
        with self.assertRaises(RuleError):
            compare.record("En trop", first)
        self.assertEqual(len(compare.matrix()["names"]), MAX_COMPARISON_PATHS)

    def test_failed_locked_detour_does_not_pollute_comparison(self):
        project = deepcopy(self.project)
        project.story["scenes"][0]["choices"][2].pop("effects")
        project.validate(self.content)
        lab = WorldTravelLab(
            self.content, project, "main", "garden", "escape")
        lab.run_to_stop()
        compare = WorldRouteComparison(lab)
        snapshot = lab.session.recording()
        result = compare.compare_choices()
        self.assertEqual(len(result["added"]), 2)
        self.assertEqual(len(result["failures"]), 1)
        self.assertEqual(result["failures"][0]["choice"], "north")
        self.assertEqual(lab.session.recording(), snapshot)

    def test_recorded_path_uses_real_rules_and_does_not_mutate_saved_game(self):
        compare = WorldRouteComparison(self.lab)
        candidate = compare.fork()
        candidate.choose("forward")
        candidate.run_to_stop()
        compare.record("Événement 1 puis péage", candidate)
        # A pending second event is still a valid comparable trajectory.
        self.assertEqual(compare.detail("Événement 1 puis péage")["state"]["step"], 6)
        self.assertTrue(any(row["metric"] == "Situation" and
                            row["values"] == ["Dialogue : toll"]
                            for row in compare.matrix()["rows"]))
        self.assertEqual(self.project.to_dict(), self.initial_project)
        self.assertEqual(self.content.to_dict(), self.initial_content)

    def test_cannot_fork_without_a_real_pending_choice(self):
        lab = WorldTravelLab(
            self.content, self.project, "main", "garden", "escape")
        with self.assertRaises(RuleError):
            WorldRouteComparison(lab)
