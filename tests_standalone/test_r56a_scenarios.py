"""R56.A regression gates: source pinning, CT, fixed tick and R55 economy."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r56_scenarios import (
    KIND, build_scenario, main, run_scenario, validate_scenario)
from drawtemp.sdk.r40_starters import create_starter_pair

REVISION = "a" * 40


def adventure():
    content, project = create_starter_pair("r40-adventure")
    steps = [
        {"operation": "route_realtime_step", "args": [0, 0],
         "expect": [{"path": ["mode"], "equals": "campaign"}]},
        {"operation": "route_realtime_step", "args": [1, 0],
         "expect": [{"path": ["scene_route", "current"], "equals": "arrival"}]},
    ]
    doc = build_scenario(content, project, identifier="r56adventure",
                         starter="r40-adventure", revision=REVISION, steps=steps)
    return content, project, doc


class R56GameplayQATests(unittest.TestCase):
    def test_fixed_tick_replay_twice_and_canonical_resume(self):
        content, project, doc = adventure()
        original = deepcopy(doc)
        report = run_scenario(doc, content, project, revision=REVISION)
        self.assertEqual(report["status"], "passed", report)
        self.assertTrue(report["replay_verified"])
        self.assertEqual([x["step"] for x in report["trace"]], [0, 1, 2])
        self.assertTrue(all(x["checkpoint"] for x in report["trace"]))
        self.assertEqual(doc, original)
        self.assertFalse(report["revision_independently_attested"])
        self.assertFalse(report["release_certified"])
        self.assertEqual(report["trace"], run_scenario(
            doc, content, project, revision=REVISION)["trace"])

    def test_injected_regression_produces_first_failing_prefix(self):
        content, project, doc = adventure()
        doc["steps"][1]["expect"][0]["equals"] = "wrong-scene"
        report = run_scenario(doc, content, project, revision=REVISION)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["counterexample"]["category"], "invariant")
        self.assertEqual(report["counterexample"]["step"], 2)
        self.assertEqual(report["counterexample"]["prefix"], doc["steps"])
        self.assertFalse(report["replay_verified"])

    def test_wrong_revision_blocks_without_execution(self):
        content, project, doc = adventure()
        report = run_scenario(doc, content, project, revision="b" * 40)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["steps_executed"], 0)
        self.assertEqual(report["counterexample"]["category"], "revision_drift")

    def test_wrong_project_blocks_from_digest(self):
        content, _, doc = adventure()
        _, other = create_starter_pair("r40-metroidvania")
        report = run_scenario(doc, content, other, revision=REVISION)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["counterexample"]["category"], "source_drift")

    def test_disallow_arbitrary_methods_and_invalid_seed(self):
        content, project, doc = adventure()
        for operation in ("save", "__init__", "from_recording", "system_preview"):
            with self.subTest(operation=operation):
                invalid = deepcopy(doc)
                invalid["steps"][0]["operation"] = operation
                with self.assertRaises(ValueError):
                    run_scenario(invalid, content, project, revision=REVISION)
        for seed in (True, -1, 2**40):
            invalid = deepcopy(doc)
            invalid["seed"] = seed
            with self.assertRaises(ValueError):
                validate_scenario(invalid)

    def test_ct_story_action_stays_in_canonical_runtime(self):
        content, project = create_starter_pair("r40-srpg")
        doc = build_scenario(
            content, project, identifier="r56srpg", starter="r40-srpg",
            revision=REVISION, steps=[
                {"operation": "choose_story_option", "args": ["enter"],
                 "expect": [{"path": ["mode"], "equals": "campaign"}]},
            ])
        report = run_scenario(doc, content, project, revision=REVISION)
        self.assertEqual(report["status"], "passed", report)

    def test_r55_system_tick_invariants_with_real_game_project(self):
        from examples.r55_micro_economy import build_example
        content, project = build_example()
        doc = build_scenario(
            content, project, identifier="r56economy", starter="r55-fixture",
            revision=REVISION, steps=[
                {"operation": "system_advance", "args": [2],
                 "expect": [{"path": ["systems", "tick"], "equals": 2}]},
                {"operation": "system_advance", "args": [2],
                 "expect": [{"path": ["systems", "tick"], "equals": 4}]},
            ])
        report = run_scenario(doc, content, project, revision=REVISION)
        self.assertEqual(report["status"], "passed", report)

    def test_schema_and_limits_are_fail_closed(self):
        content, project, doc = adventure()
        self.assertEqual(doc["kind"], KIND)
        invalid = [
            {**doc, "schema": True}, {**doc, "seed": True},
            {**doc, "steps": []}, {**doc, "steps": doc["steps"] * 129},
            {**doc, "surprise": 1}, {**doc, "content_digest": "0" * 65},
        ]
        for candidate in invalid:
            with self.subTest(candidate=str(candidate)[:40]):
                with self.assertRaises(ValueError):
                    validate_scenario(candidate)
        with self.assertRaises(ValueError):
            run_scenario(doc, content, project, revision=REVISION,
                         checkpoint_every=True)

    def test_cli_writes_report_never_overwrites_source(self):
        _, _, doc = adventure()
        with TemporaryDirectory() as temp:
            source = Path(temp) / "case.json"
            output = Path(temp) / "report.json"
            source.write_text(json.dumps(doc), encoding="utf-8")
            self.assertEqual(main(["--scenario", str(source), "--revision",
                                   REVISION, "--output", str(output)]), 0)
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "passed")
            self.assertFalse(saved["release_certified"])
            self.assertEqual(main(["--scenario", str(source), "--revision",
                                   REVISION, "--output", str(source)]), 2)
            source.write_text('{"kind":"a","kind":"b"}', encoding="utf-8")
            self.assertEqual(main(["--scenario", str(source),
                                   "--revision", REVISION]), 2)


if __name__ == "__main__":
    unittest.main()
