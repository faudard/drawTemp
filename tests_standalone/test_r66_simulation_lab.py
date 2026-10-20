"""R66.A/B-headless/C-headless: deterministic, read-only observational lab."""
from copy import deepcopy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from drawtemp.sdk.r66_simulation_lab import (
    SimulationLabError, SimulationTraceLab, analyze_batch, compare_batches,
    validate_trace,
)


def trace(seed=1, days=30, *, price=2, idle=False):
    """Synthetic input EVENTS only; never claims to execute GameSession."""
    events = []
    for day in range(days):
        if idle and 11 <= day <= 15:
            continue
        start = f"harvest-{day}"
        events.extend([
            {"id": start, "tick": day * 24, "kind": "produce",
             "resource": "food", "quantity": price, "source": None,
             "target": "farm", "depends_on": [], "cause": "fixture-harvest"},
            {"id": f"ship-{day}", "tick": day * 24 + 1,
             "kind": "transfer", "resource": "food", "quantity": 1,
             "source": "farm", "target": "village", "depends_on": [start],
             "cause": "fixture-trade"},
            {"id": f"eat-{day}", "tick": day * 24 + 2,
             "kind": "consume", "resource": "food", "quantity": 1,
             "source": "village", "target": None,
             "depends_on": [f"ship-{day}"], "cause": "fixture-consumption"},
        ])
    return {"schema": 1, "seed": seed, "days": days, "ticks_per_day": 24,
            "accounts": {"farm": {"food": 5}, "village": {"food": 0}},
            "events": events}


class ContractTests(unittest.TestCase):
    def test_detached_validation_and_fail_closed_inputs(self):
        original = trace()
        validated = validate_trace(original)
        validated["events"][0]["quantity"] = 999
        self.assertNotEqual(original, validated)
        changes = [
            ("schema", 2, "unsupported_schema"),
            ("seed", True, "invalid_integer"),
            ("days", 366, "invalid_integer"),
            ("ticks_per_day", 0, "invalid_integer"),
        ]
        for key, value, code in changes:
            with self.subTest(key=key):
                bad = trace()
                bad[key] = value
                with self.assertRaises(SimulationLabError) as cm:
                    validate_trace(bad)
                self.assertEqual(cm.exception.code, code)
        bad = trace()
        bad["events"][1]["depends_on"] = ["eat-29"]
        with self.assertRaisesRegex(SimulationLabError, "Dependencies"):
            validate_trace(bad)
        bad = trace()
        bad["events"][2]["id"] = bad["events"][0]["id"]
        with self.assertRaises(SimulationLabError) as cm:
            validate_trace(bad)
        self.assertEqual(cm.exception.code, "duplicate_event")
        bad = trace()
        bad["events"][4]["tick"] = 0  # follows event at tick 24
        with self.assertRaises(SimulationLabError) as cm:
            validate_trace(bad)
        self.assertEqual(cm.exception.code, "event_order")

    def test_overdraft_has_actionable_error_and_seek_is_atomic(self):
        t = trace(days=1)
        t["events"][1]["quantity"] = 100
        lab = SimulationTraceLab(t)
        original = lab.snapshot()
        with self.assertRaises(SimulationLabError) as cm:
            lab.run()
        self.assertEqual(cm.exception.code, "insufficient_resource")
        self.assertEqual(lab.snapshot(), original)
        self.assertEqual(analyze_batch([t])["samples"][0]["status"], "failed")


class DeterminismTests(unittest.TestCase):
    def test_step_rewind_seek_and_replay_are_independent(self):
        t = trace(days=30)
        original = deepcopy(t)
        lab = SimulationTraceLab(t)
        start = lab.snapshot()
        lab.step(12)
        partial = lab.snapshot()
        self.assertEqual(partial["position"], 12)
        lab.rewind(5)
        self.assertEqual(lab.step(5), partial)
        end = lab.run()
        self.assertEqual(end["totals"]["food"], 5 + 30 * 2 - 30)
        self.assertEqual(end["created"]["food"], 60)
        self.assertEqual(end["consumed"]["food"], 30)
        end["balances"]["farm"]["food"] = -100
        self.assertNotEqual(lab.snapshot()["balances"]["farm"]["food"], -100)
        self.assertEqual(lab.seek(0), start)
        self.assertEqual(lab.run()["totals"]["food"], 35)
        self.assertEqual(t, original)
        self.assertEqual(SimulationTraceLab(t).run(), lab.run())

    def test_cancel_does_not_return_false_completion(self):
        lab = SimulationTraceLab(trace())
        lab.step()
        lab.cancel()
        self.assertEqual(lab.remaining, 89)
        with self.assertRaises(SimulationLabError) as cm:
            lab.step()
        self.assertEqual(cm.exception.code, "cancelled")
        self.assertTrue(lab.snapshot()["cancelled"])
        result = analyze_batch([trace(1), trace(2)], cancel_after=1)
        self.assertEqual(result["status"], "cancelled")
        with self.assertRaises(SimulationLabError):
            compare_batches(result, result)

    def test_no_ui_or_wall_clock_dependency(self):
        root = Path(__file__).resolve().parents[1]
        code = """
import sys
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('tkinter','PySide6','PyQt6'):
            raise RuntimeError('Unexpected GUI import: '+fullname)
sys.meta_path.insert(0, Guard())
from drawtemp.sdk.r66_simulation_lab import SimulationTraceLab
assert SimulationTraceLab({'schema':1,'seed':1,'days':1,'ticks_per_day':1,
'accounts': {'alice':{'wood':0}}, 'events':[]}).run()['position'] == 0
"""
        result = subprocess.run([sys.executable, "-c", code], cwd=root,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


class BatchTests(unittest.TestCase):
    def test_repeatable_30_day_economy_observation_and_drift(self):
        runs = [trace(seed) for seed in (2, 17, 81)]
        baseline = analyze_batch(runs)
        self.assertEqual(baseline, analyze_batch(deepcopy(runs)))
        self.assertEqual(baseline["status"], "completed")
        self.assertEqual(len(baseline["samples"]), 3)
        self.assertEqual(baseline["samples"][0]["events_p99"], 3)
        self.assertEqual(baseline["samples"][0]["closing_totals"]["food"], 35)
        slower = analyze_batch([trace(seed, price=3) for seed in (2, 17, 81)])
        diff = compare_batches(baseline, slower)
        self.assertFalse(diff["same_deterministic_report"])
        self.assertEqual([row["resource_deltas"]["food"] for row in diff["per_seed"]],
                         [30, 30, 30])
        self.assertTrue(compare_batches(baseline, baseline)["same_deterministic_report"])
        self.assertEqual(json.loads(json.dumps(baseline)), baseline)

    def test_idle_warnings_do_not_claim_proven_softlock(self):
        report = analyze_batch([trace(idle=True)], idle_days=3)
        sample = report["samples"][0]
        self.assertEqual(sample["status"], "warning")
        self.assertEqual(sample["idle_windows"], [11])
        self.assertEqual(sample["longest_idle_days"], 5)
        self.assertEqual(report["status"], "completed")

    def test_batch_gates_invalid_seeds_and_horizon(self):
        for traces in ([trace(2), trace(2)], [trace(1), trace(2, days=1)]):
            with self.assertRaises(SimulationLabError):
                analyze_batch(traces)
        with self.assertRaises(SimulationLabError):
            analyze_batch([trace()], idle_days=0)
        with self.assertRaises(SimulationLabError):
            analyze_batch([])
        with self.assertRaises(SimulationLabError):
            analyze_batch([trace()] * 33)
        baseline = analyze_batch([trace(1)])
        with self.assertRaises(SimulationLabError):
            compare_batches(baseline, analyze_batch([trace(2)]))


if __name__ == "__main__":
    unittest.main()
