"""R5.14 route sandbox: real StoryBook choices, symbolic outcomes, branching and isolation."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.reliability_gate import fixture
from sporebound.campaign_flow_simulation import CampaignSimulation
from sporebound.game_project import save_slot
from sporebound.model import RuleError


class CampaignSimulationTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = fixture()
        self.project.campaign_flow = {
            "gates": {
                "walls": {"all": [
                    {"completed_mission": "gate"},
                    {"flag": "reputation_village", "gte": 2},
                ]},
                "throne": {"completed_mission": "walls"},
            },
            "outcomes": {
                "gate": {"victory": [
                    {"kind": "add_flag", "flag": "reputation_village", "amount": 2},
                    {"kind": "wound", "hero": "captain", "wound": "arm_injury"},
                ]},
                "walls": {"victory": [
                    {"kind": "heal_wound", "hero": "captain", "wound": "arm_injury"},
                    {"kind": "set_flag", "flag": "fortification_gate", "value": "open"},
                ]},
            },
            "endings": {
                "mercy": {"flag": "ending", "eq": "mercy"},
                "occupation": {"flag": "ending", "eq": "occupation"},
            },
        }
        self.project.validate(self.content)

    def simulator(self, **kwargs):
        return CampaignSimulation(self.content, self.project, "main", **kwargs)

    def test_two_endings_from_same_epilogue_and_comparison(self):
        original = deepcopy(self.project.to_dict())
        sim = self.simulator()
        self.assertEqual(sim.actions()[0]["kind"], "choice")
        self.assertEqual(sim.actions()[0]["id"], "assault")
        sim.choose("assault")
        self.assertEqual([x["id"] for x in sim.actions() if
                          x["outcome"] == "victory"], ["gate"])
        sim.resolve("gate", "victory")
        self.assertEqual(sim.inspect()["resources"]["gold"], 100)
        self.assertIn("arm_injury", sim.snapshot().hero("captain").wounds)
        self.assertIn("walls", [x["id"] for x in sim.actions()])
        sim.resolve("walls", "victory")
        self.assertEqual(sim.snapshot().hero("captain").wounds, [])
        self.assertEqual(sim.inspect()["variables"]["fortification_gate"], "open")
        sim.resolve("throne", "victory")
        junction = sim.cursor
        self.assertEqual([x["id"] for x in sim.actions()], ["spare", "occupy"])
        self.assertEqual(sim.inspect()["resources"]["gold"], 300)
        self.assertEqual(sim.snapshot().heroes["captain"].xp, 0)
        self.assertEqual(sim.snapshot().tracked_battles, [])
        sim.choose("spare")
        spare = sim.cursor
        self.assertEqual(sim.inspect()["endings"], ["mercy"])
        self.assertEqual(sim.inspect()["resources"]["gold"], 325)
        sim.select(junction)
        sim.choose("occupy")
        occupy = sim.cursor
        self.assertEqual(sim.inspect()["endings"], ["occupation"])
        self.assertEqual(sim.inspect()["resources"]["gold"], 300)
        diff = sim.compare(spare, occupy)
        self.assertEqual(diff["common_ancestor"], junction)
        self.assertEqual(diff["left_endings"], ["mercy"])
        self.assertEqual(diff["right_endings"], ["occupation"])
        self.assertTrue(any(row["path"] == "resources.gold"
                            for row in diff["changed"]))
        self.assertTrue(any(row["path"] == "variables.ending"
                            for row in diff["changed"]))
        self.assertTrue(diff["symbolic_only"])
        self.assertEqual(sim.coverage()["endings_witnessed"],
                         ["mercy", "occupation"])
        self.assertEqual(self.project.to_dict(), original)

    def test_defeat_then_victory_distinct_outcomes_and_no_reward_farming(self):
        self.project.campaign_flow["outcomes"]["gate"]["defeat"] = [
            {"kind": "set_flag", "flag": "enemy_pressure", "value": True}]
        sim = self.simulator()
        sim.choose("assault")
        before = sim.cursor
        sim.resolve("gate", "defeat")
        defeat = sim.cursor
        self.assertNotIn("gate", sim.snapshot().completed)
        self.assertTrue(sim.inspect()["variables"]["enemy_pressure"])
        self.assertIn("gate", [a["id"] for a in sim.actions()])
        self.assertEqual(sim.snapshot().flow_ledger, ["gate:defeat"])
        sim.resolve("gate", "victory")
        self.assertEqual(sim.snapshot().flow_ledger,
                         ["gate:defeat", "gate:victory"])
        self.assertEqual(sim.snapshot().completed, ["gate"])
        self.assertEqual(sim.inspect()["resources"]["gold"], 100)
        self.assertNotIn("gate", [x["id"] for x in sim.actions()])
        sim.select(before)
        sim.resolve("gate", "victory")
        self.assertNotIn("enemy_pressure", sim.inspect()["variables"])
        self.assertEqual(sim.compare(defeat, sim.cursor)["common_ancestor"],
                         before)

    def test_reject_stale_and_illegal_ops_without_cursor_or_tree_mutation(self):
        sim = self.simulator(max_nodes=4)
        before = sim.tree()
        with self.assertRaises(RuleError):
            sim.resolve("gate", "victory")  # mandatory entry dialogue
        with self.assertRaises(RuleError):
            sim.choose("missing")
        with self.assertRaises(RuleError):
            sim.select(999)
        self.assertEqual(sim.tree(), before)
        sim.choose("assault")
        with self.assertRaises(RuleError):
            sim.resolve("walls", "victory")  # gated, even though story unlocked
        self.assertEqual(sim.size, 2)
        sim.fork("try another route")
        self.assertEqual(sim.size, 3)
        sim.fork("again")
        with self.assertRaisesRegex(RuleError, "budget"):
            sim.fork("must fail")
        self.assertEqual(sim.size, 4)
        self.assertEqual(sim.cursor, 3)
        with self.assertRaises(RuleError):
            sim.fork("")
        self.assertEqual(sim.size, 4)

    def test_fork_snapshot_isolation_and_no_slot_or_project_writes(self):
        initial = self.project.new_game("main", self.content)
        with TemporaryDirectory() as folder:
            target = Path(folder) / "profile.json"
            path = save_slot(target, self.project, self.content, "main", 1,
                             initial)
            before = path.read_bytes()
            authored = deepcopy(self.project.to_dict())
            sim = self.simulator(progress=initial)
            sim.choose("assault")
            sim.resolve("gate", "victory")
            progress = sim.snapshot()
            progress.story_flags["reputation_village"] = 999
            progress.gold = 999
            self.assertEqual(sim.inspect()["variables"]["reputation_village"], 2)
            exposed_node = sim.node()
            exposed_node.progress.story_flags["reputation_village"] = -999
            self.assertEqual(sim.inspect()["variables"]["reputation_village"], 2)
            self.assertEqual(initial.story_flags, {})
            sim.select(0)
            sim.fork("alternate checkpoint")
            self.assertEqual(sim.snapshot().completed, [])
            self.assertEqual(sim.snapshot().story_pending, "briefing")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(self.project.to_dict(), authored)
            self.assertEqual(list(Path(folder).rglob("*.json")), [path])

    def test_bounded_depth_and_state_identity_validation(self):
        initial = self.project.new_game("main", self.content)
        changed = deepcopy(self.project)
        changed.campaign_flow["gates"]["gate"] = {"gold_gte": 100}
        changed.validate(self.content)
        with self.assertRaisesRegex(RuleError, "differs"):
            CampaignSimulation(self.content, changed, "main",
                               progress=initial)
        sim = self.simulator(max_depth=1)
        sim.choose("assault")
        with self.assertRaisesRegex(RuleError, "depth"):
            sim.fork("too deep")
        self.assertEqual(sim.size, 2)
        self.assertEqual(sim.inspect()["symbolic_only"], True)


if __name__ == "__main__":
    unittest.main()
