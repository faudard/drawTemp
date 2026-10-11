"""3.7.5 benchmark matrix is explicit and produces real, isolated measurements."""
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from scripts.collect_renderers_375 import collect, plan, summarize


class RendererCollectionTests(TestCase):
    def test_full_matrix_has_three_isolated_repeats_per_case(self):
        rows = plan()
        self.assertEqual(len(rows), 54)
        self.assertEqual(len({(row["backend"], row["actors"], row["scale"])
                              for row in rows}), 18)
        self.assertEqual(sum(row["backend"] == "tk" for row in rows), 18)
        for row in rows:
            self.assertIn(row["repeat"], (1, 2, 3))

    def test_invalid_cases_are_rejected(self):
        for options in (
            {"backends": ["other"]}, {"actors": [17]},
            {"scales": [3]}, {"repeats": 0}, {"repeats": 11},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                plan(**options)

    def test_summary_keeps_stability_and_sample_count(self):
        samples = [
            {"backend": "tk", "actors": 80, "scale": 1,
             "p50_ms": n, "p95_ms": n + 10}
            for n in (5, 3, 4)
        ]
        result = summarize(samples)
        self.assertEqual(result, [{
            "backend": "tk", "actors": 80, "scale": 1, "runs": 3,
            "median_p50_ms": 4.0, "median_p95_ms": 14.0,
            "max_p95_ms": 15.0, "within_33ms_heuristic": True,
        }])

    @patch("scripts.collect_renderers_375.subprocess.run")
    def test_each_case_runs_fresh_process(self, run):
        row = plan(backends=("tk",), actors=(20,), scales=(1,), repeats=2)
        result = {"backend": "tk", "actors": 20, "scale": 1, "frames": 20,
                  "p50_ms": 1.1, "p95_ms": 2.3}
        run.return_value = SimpleNamespace(returncode=0,
                                           stdout=json.dumps(result), stderr="")
        readings = collect(row, frames=20, timeout=30)
        self.assertEqual(len(readings), 2)
        self.assertEqual([s["repeat"] for s in readings], [1, 2])
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["timeout"], 30)
            self.assertTrue(call.args[0][1].endswith("benchmark_renderers_375.py"))

    @patch("scripts.collect_renderers_375.subprocess.run")
    def test_failure_cannot_create_fake_timing(self, run):
        run.return_value = SimpleNamespace(returncode=1, stdout="", stderr="No GUI")
        with self.assertRaisesRegex(RuntimeError, "renderer failed"):
            collect(plan(backends=("tk",), actors=(20,),
                         scales=(1,), repeats=1), frames=20, timeout=10)
