"""R29.B: concrete key/door solvability, branch counterexamples and proof limits."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r29b_gameplay import (
    analyze_action_scene, audit_action_replay, audit_dungeon_puzzle,
)
from scripts.audit_r29b_gameplay import main


def scene(*, chest=True, wrong_door=False, enemies=False):
    obj = [{"id": "exit", "kind": "door", "pos": [2, 2],
            "item": "", "requires": "key"}]
    if chest:
        obj.append({"id": "key_chest", "kind": "chest", "pos": [1, 1],
                    "item": "key", "requires": ""})
    if wrong_door:
        obj.append({"id": "bait", "kind": "door", "pos": [1, 3],
                    "item": "", "requires": "key"})
    return {"id": "ruins", "width": 5, "height": 5,
            "walls": [[2, y] for y in (0, 1, 3, 4)],
            "hero": {"pos": [1, 2], "hp": 12},
            "enemies": ([{"id": "wolf", "pos": [4, 4], "hp": 2, "patrol": []}]
                        if enemies else []), "objects": obj}


class R29BGameplayTests(unittest.TestCase):
    def test_key_then_open_door_yields_executable_abstract_witness(self):
        source = scene()
        before = deepcopy(source)
        report = analyze_action_scene(source, [[4, 2]])
        self.assertEqual(source, before)
        self.assertEqual(report["status"], "static_reachable")
        self.assertTrue(report["complete"])
        self.assertEqual(report["dead_end_states"], 0)
        kinds = [x.get("id", x["kind"]) for x in report["reachable_goals"][0]["witness"]]
        self.assertIn("key_chest", kinds)
        self.assertIn("exit", kinds)
        self.assertLess(kinds.index("key_chest"), kinds.index("exit"))
        self.assertFalse(report["runtime_certified"])

    def test_missing_key_detects_unreachable_goal(self):
        report = analyze_action_scene(scene(chest=False), [[4, 2]])
        self.assertEqual(report["status"], "softlock_risk")
        self.assertEqual(report["unreachable_goals"], [[4, 2]])
        self.assertGreater(report["dead_end_states"], 0)
        self.assertTrue(report["counterexamples"])

    def test_wrong_consumable_key_choice_provides_counterexample(self):
        report = analyze_action_scene(scene(wrong_door=True), [[4, 2]])
        self.assertEqual(report["status"], "softlock_risk")
        self.assertFalse(report["unreachable_goals"])
        self.assertGreater(report["dead_end_states"], 0)
        self.assertTrue(any("bait" in witness["opened"] for witness in report["counterexamples"]),
                        report["counterexamples"])

    def test_hard_budget_never_produces_false_exhaustive_certificate(self):
        for cap in (1, 2, 3):
            with self.subTest(cap=cap):
                report = analyze_action_scene(scene(), [[4, 2]], state_budget=cap)
                self.assertEqual(report["status"], "inconclusive")
                self.assertFalse(report["complete"])
                self.assertIsNone(report["dead_end_states"])

    def test_enemy_analysis_explicitly_excludes_combat_even_when_reachable(self):
        report = analyze_action_scene(scene(enemies=True), [[4, 2]])
        self.assertEqual(report["status"], "static_reachable")
        self.assertTrue(any("enemy" in s for s in report["limitations"]))
        self.assertFalse(report["runtime_certified"])

    def test_input_validation_and_no_mutation(self):
        original = scene()
        for invalid, goals in (
            ({**original, "width": True}, [[4, 2]]),
            ({**original, "walls": [[2, 1], [2, 1]]}, [[4, 2]]),
            ({**original, "objects": original["objects"] * 13}, [[4, 2]]),
            (original, []),
            (original, [[4, 2], [4, 2]]),
            (original, [[99, 2]]),
        ):
            with self.subTest(invalid=invalid, goals=goals):
                with self.assertRaises(ValueError):
                    analyze_action_scene(invalid, goals)
        self.assertEqual(original, scene())
        with self.assertRaises(ValueError):
            analyze_action_scene(original, [[4, 2]], state_budget=True)

    def test_r26_replay_fails_closed_without_runtime_and_compares_when_present(self):
        try:
            from sporebound.action_runtime import ActionRuntime
        except ModuleNotFoundError:
            missing = audit_action_replay(scene(), [{"tick": 1}], checkpoint_every=1)
            self.assertEqual(missing["status"], "blocked")
            self.assertFalse(missing["replay_verified"])
        else:
            audited = audit_action_replay(scene(), [
                {"tick": 1}, {"tick": 2, "interact": "key_chest"},
                {"tick": 3, "interact": "exit"}, {"tick": 4, "dx": 1}],
                checkpoint_every=2)
            self.assertEqual(audited["status"], "partial")
            self.assertTrue(audited["replay_verified"])
            self.assertEqual(len(audited["checkpoints"]), 2)
            self.assertFalse(audited["runtime_certified"])
        with self.assertRaises(ValueError):
            audit_action_replay(scene(), [{"tick": 1}], checkpoint_every=0)

    def test_r27_adapter_interprets_incomplete_and_unreachable_correctly(self):
        class Dungeon:
            def __init__(self, value):
                self.value = value
            def puzzle_report(self, *, state_budget):
                return deepcopy(self.value)
        base = {"complete": True, "unreachable_goals": [],
                "unreachable_objects": [], "warnings": [], "states": 11}
        self.assertEqual(audit_dungeon_puzzle(Dungeon(base))["status"], "static_reachable")
        self.assertEqual(audit_dungeon_puzzle(Dungeon({**base, "complete": False}))["status"], "inconclusive")
        self.assertEqual(audit_dungeon_puzzle(Dungeon({**base, "unreachable_goals": [[3, 2]]}))["status"], "softlock_risk")
        with self.assertRaises(ValueError):
            audit_dungeon_puzzle(Dungeon({"complete": True}))

    def test_cli_report_retains_no_go_and_does_not_overwrite_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "scene.json"
            source.write_text(json.dumps(scene()), encoding="utf-8")
            output = root / "result.json"
            self.assertEqual(main(["--scene", str(source), "--goal", "4,2",
                                   "--report", str(output)]), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["static_analysis"]["status"], "static_reachable")
            self.assertFalse(report["release_ready"])
            self.assertEqual(report["decision"], "no-go")
            self.assertEqual(main(["--scene", str(source), "--goal", "4,2",
                                   "--report", str(output), "--require-solved"]), 0)
            self.assertEqual(main(["--scene", str(source), "--goal", "4,2",
                                   "--state-budget", "1", "--report", str(output),
                                   "--require-solved"]), 2)
            self.assertEqual(json.loads(source.read_text(encoding="utf-8")), scene())


if __name__ == "__main__":
    unittest.main()
