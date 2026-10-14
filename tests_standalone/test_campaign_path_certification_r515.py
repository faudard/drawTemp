"""R5.15 certificate gates: only actual Battle commands and disk replay pass."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from examples.reliability_gate import fixture
from scripts.certify_campaign_paths import run as run_suite
from sporebound.campaign_flow_simulation import CampaignSimulation
from sporebound.campaign_path_certification import (
    certificate_coverage, certify_path, validate_plan)
from sporebound.game_project import GameProject
from sporebound.model import RuleError


class CampaignPathCertificationTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = fixture()
        self.project.campaign_flow = {
            "gates": {"walls": {"completed_mission": "gate"},
                      "throne": {"completed_mission": "walls"}},
            "outcomes": {"gate": {"victory": [
                {"kind": "add_flag", "flag": "supplies_player", "amount": 2},
                {"kind": "wound", "hero": "captain", "wound": "arm_injury"},
            ]}, "walls": {"victory": [
                {"kind": "heal_wound", "hero": "captain", "wound": "arm_injury"},
                {"kind": "set_flag", "flag": "fortification_gate", "value": "open"},
            ]}},
            "endings": {"mercy": {"flag": "ending", "eq": "mercy"},
                        "occupation": {"flag": "ending", "eq": "occupation"}},
        }
        self.project.validate(self.content)
        self.authored = deepcopy(self.project.to_dict())

    @staticmethod
    def steps(ending):
        return [
            {"kind": "choice", "id": "assault"},
            {"kind": "mission", "id": "gate", "outcome": "victory"},
            {"kind": "mission", "id": "walls", "outcome": "victory"},
            {"kind": "mission", "id": "throne", "outcome": "victory"},
            {"kind": "choice", "id": ending},
        ]

    def plan(self, ending):
        return {"id": "castle_" + ending, "campaign": "main", "seed": 7,
                "steps": self.steps(ending),
                "expect": {"completed": ["gate", "walls", "throne"],
                           "endings": ["mercy" if ending == "spare"
                                       else "occupation"]}}

    def test_real_paths_are_certified_for_both_endings_with_checkpoint_parity(self):
        records = []
        for choice in ("spare", "occupy"):
            with self.subTest(choice=choice):
                report = certify_path(self.content, self.project,
                                      self.plan(choice),
                                      max_commands=800, checkpoint_every=5)
                self.assertEqual(report["status"], "CERTIFIED")
                self.assertEqual(report["evidence"]["tactical_battles"], 3)
                self.assertGreater(report["evidence"]["commands"], 3)
                self.assertGreater(report["evidence"]["checkpoints"], 3)
                self.assertTrue(report["evidence"]["uninterrupted_equal_resumed"])
                self.assertEqual(report["observed"]["completed"],
                                 ["gate", "walls", "throne"])
                self.assertEqual(report["observed"]["gold"],
                                 325 if choice == "spare" else 300)
                self.assertEqual(report["observed"]["variables"]["supplies_player"], 2)
                self.assertEqual(report["observed"]["variables"]["fortification_gate"], "open")
                self.assertEqual(report["observed"]["consequences"],
                                 ["gate:victory", "walls:victory"])
                self.assertEqual(len([r for r in report["evidence"]["timeline"]
                                      if r["kind"] == "battle"]), 3)
                records.append(report)
        coverage = certificate_coverage(self.project, records,
                                        required_ids=["castle_spare", "castle_occupy"])
        self.assertTrue(coverage["complete_for_required_cases"])
        self.assertTrue(coverage["complete_for_declared_endings"])
        self.assertEqual(coverage["uncertified_endings"], [])
        self.assertEqual(self.project.to_dict(), self.authored)

    def test_unverified_simulation_does_not_get_certified_until_replayed(self):
        simulator = CampaignSimulation(self.content, self.project, "main")
        simulator.choose("assault")
        simulator.resolve("gate", "victory")
        simulator.resolve("walls", "victory")
        simulator.resolve("throne", "victory")
        simulator.choose("spare")
        plan = simulator.certification_plan(seed=7)
        self.assertEqual(plan["expect"]["endings"], ["mercy"])
        self.assertEqual(plan["steps"], self.steps("spare"))
        self.assertNotIn("status", plan)
        self.assertTrue(simulator.node().verified_battle is False)
        report = certify_path(self.content, self.project, plan,
                              max_commands=800)
        self.assertEqual(report["status"], "CERTIFIED")
        loaded_progress = self.project.new_game("main", self.content)
        loaded = CampaignSimulation(self.content, self.project, "main",
                                    progress=loaded_progress)
        loaded.choose("assault")
        loaded.resolve("gate", "victory")
        with self.assertRaisesRegex(RuleError, "partial loaded"):
            loaded.certification_plan()

    def test_mismatched_actual_path_outcome_or_ending_rejects_certificate(self):
        wrong_ending = self.plan("spare")
        wrong_ending["expect"]["endings"] = ["occupation"]
        with self.assertRaisesRegex(RuleError, "endings differ"):
            certify_path(self.content, self.project, wrong_ending,
                         max_commands=800)
        locked = self.plan("spare")
        locked["steps"] = [locked["steps"][0], locked["steps"][2]]
        with self.assertRaisesRegex(RuleError, "locked"):
            certify_path(self.content, self.project, locked, max_commands=800)
        fake_defeat = self.plan("spare")
        fake_defeat["steps"][1]["outcome"] = "defeat"
        with self.assertRaisesRegex(RuleError, "differs from planned"):
            certify_path(self.content, self.project, fake_defeat,
                         max_commands=800)
        self.assertEqual(self.project.to_dict(), self.authored)

    def test_invalid_specs_and_budget_fail_closed(self):
        for mutate in (
            lambda p: p.update(seed=True),
            lambda p: p["steps"].append({"kind": "fake_win", "id": "gate"}),
            lambda p: p["expect"].update(endings=["not_declared"]),
            lambda p: p["steps"].clear(),
        ):
            sample = self.plan("spare")
            mutate(sample)
            with self.assertRaises(RuleError):
                validate_plan(sample, self.content, self.project)
        with self.assertRaisesRegex(RuleError, "budget"):
            certify_path(self.content, self.project, self.plan("spare"),
                         max_commands=1)
        with self.assertRaises(RuleError):
            certify_path(self.content, self.project, self.plan("spare"),
                         checkpoint_every=0)

    def test_suite_writes_failure_evidence_and_never_claims_full_coverage(self):
        valid = self.plan("spare")
        wrong = self.plan("occupy")
        wrong["expect"]["endings"] = ["mercy"]
        suite = run_suite(self.content, self.project, None,
                          {"version": 1, "cases": [valid, wrong]},
                          max_commands=800, require_all_endings=True)
        self.assertFalse(suite["verified"])
        self.assertEqual([r["status"] for r in suite["cases"]],
                         ["CERTIFIED", "FAILED"])
        self.assertEqual(suite["coverage"]["uncertified_endings"],
                         ["occupation"])
        self.assertFalse(suite["coverage"]["complete_for_required_cases"])

    def test_corrupted_or_unreadable_checkpoint_never_produces_certificate(self):
        from sporebound.persistence import SessionStore
        with patch.object(SessionStore, "load",
                          side_effect=RuleError("injected broken checkpoint")):
            with self.assertRaisesRegex(RuleError, "broken checkpoint"):
                certify_path(self.content, self.project, self.plan("spare"),
                             max_commands=800)

    def test_coverage_rejects_duplicate_certificates_and_invented_endings(self):
        sample = {"id": "castle_spare", "status": "CERTIFIED",
                  "observed": {"endings": ["mercy"]}}
        with self.assertRaisesRegex(RuleError, "Duplicate"):
            certificate_coverage(self.project, [sample, deepcopy(sample)])
        coverage = certificate_coverage(
            self.project, [sample], required_ids=("castle_spare", "castle_occupation"))
        self.assertFalse(coverage["complete_for_required_cases"])
        self.assertEqual(coverage["uncertified_endings"], ["occupation"])

    def test_existing_slot_is_never_written_when_a_route_is_certified(self):
        from sporebound.game_project import save_slot
        with TemporaryDirectory() as folder:
            base = Path(folder) / "profile.json"
            slot = save_slot(base, self.project, self.content, "main", 1,
                             self.project.new_game("main", self.content))
            original = slot.read_bytes()
            report = certify_path(self.content, self.project,
                                  self.plan("occupy"), max_commands=800)
            self.assertEqual(report["status"], "CERTIFIED")
            self.assertEqual(slot.read_bytes(), original)
            self.assertEqual(self.project.to_dict(), self.authored)


if __name__ == "__main__":
    unittest.main()
