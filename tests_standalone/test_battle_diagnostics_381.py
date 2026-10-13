"""3.8.1 seeded diagnostic trace: reproducibility, evidence and no engine changes."""
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.ai import simulate
from sporebound.battle_diagnostics import (MAX_TRACE_COMMANDS, diagnose_trace,
                                           trace_report, trace_seed)
from sporebound.battle_lab import run_lab
from sporebound.engine import Battle
from sporebound.model import Board, Content, Mission, RuleError, Unit


def arena():
    return Content({}, {"lab": Mission(
        "lab", "Diagnostics", Board(7, 5),
        [Unit("hero", "Hero", "player", (0, 1)),
         Unit("foe", "Foe", "enemy", (4, 1))])})


class DiagnosticTraceTests(unittest.TestCase):
    def test_trace_matches_seeded_sweep_and_exact_canonical_commands(self):
        content = arena()
        original = deepcopy(content.to_dict())
        report = run_lab(content, "lab", seeds=[3], max_commands=30)
        trace = trace_seed(content, "lab", seed=3, max_commands=30)
        again = trace_seed(content, "lab", seed=3, max_commands=30)
        self.assertEqual(trace, again)
        self.assertEqual(content.to_dict(), original)
        sample = report["samples"][0]
        self.assertEqual(trace["digest"], sample["digest"])
        self.assertEqual(trace["result"], sample["result"])
        self.assertEqual(trace["commands"], sample["commands"])
        self.assertTrue(trace["replay_verified"])
        self.assertEqual(len(trace["steps"]), trace["commands"])
        self.assertEqual(trace["initial"]["tick"], 0)
        self.assertEqual(trace["steps"][-1]["after"]["tick"], trace["ticks"])
        self.assertEqual(trace["steps"][-1]["after"]["result"], None
                         if trace["result"] == "limit" else trace["result"])
        commands = [step["command"] for step in trace["steps"]]
        battle = Battle(content, "lab", seed=3)
        for command in commands:
            battle.execute(command)
        self.assertEqual(battle.digest(), trace["digest"])
        self.assertEqual(Battle.replay(battle.recording()).digest(),
                         trace["digest"])
        self.assertEqual(trace["diagnostics"], diagnose_trace(
            trace["steps"], trace["result"]))

    def test_pre_post_hooks_leave_simulation_equivalent(self):
        a = Battle(arena(), "lab", seed=17)
        b = Battle(arena(), "lab", seed=17)
        before, after = [], []
        sampled = simulate(a, 24, observer=lambda battle, cmd: before.append(
            (battle.tick, deepcopy(cmd))),
            after_command=lambda battle, cmd: after.append(
                (battle.tick, deepcopy(cmd))))
        ordinary = simulate(b, 24)
        self.assertEqual(sampled, ordinary)
        self.assertEqual(a.recording()["commands"], b.recording()["commands"])
        self.assertEqual(len(before), len(after))
        self.assertEqual(len(before), len(a.commands))

    def test_diagnostic_evidence_is_explicit_and_reproducible(self):
        steps = []
        for n in range(1, 9):
            steps.append({"index": n, "actor": "idle", "team": "enemy",
                          "command": {"kind": "end"}, "progress": False,
                          "events": [{"kind": "heal", "unit": "idle", "amount": 0}]
                          if n == 2 else [{"kind": "cast_failed", "unit": "idle"}]
                          if n == 3 else []})
        diagnostics = diagnose_trace(steps, "limit", stall_window=5,
                                     idle_activations=4)
        codes = [item["code"] for item in diagnostics["findings"]]
        self.assertIn("repeat_idle", codes)
        self.assertIn("zero_effect_heal", codes)
        self.assertIn("failed_cast", codes)
        self.assertIn("command_budget", codes)
        self.assertIn("no_progress_window", codes)
        self.assertEqual(diagnostics["longest_no_progress_commands"], 8)
        self.assertEqual(diagnose_trace(steps, "victory", stall_window=5)["counts"].get(
            "no_progress_window", 0), 0)

    def test_trace_json_and_input_validation(self):
        content = arena()
        report = trace_seed(content, "lab", seed=0, max_commands=10)
        with TemporaryDirectory() as root:
            path = Path(root) / "trace.json"
            trace_report(path, report)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), report)
        for seed, commands in ((-1, 10), (2**32, 10), (3, 0),
                               (3, MAX_TRACE_COMMANDS + 1)):
            with self.subTest(seed=seed, commands=commands):
                with self.assertRaises(RuleError):
                    trace_seed(content, "lab", seed=seed, max_commands=commands)
        with self.assertRaises(RuleError):
            trace_seed(content, "absent", seed=2)


if __name__ == "__main__":
    unittest.main()
