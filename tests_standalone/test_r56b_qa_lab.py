"""R56.B QA Lab: bounded real GameSession batches, navigation and diffs."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r56_lab import (
    KIND, build_suite, capture_case, diff_batches, inspect_case,
    read_report, read_suite, replay_to_step, run_batch, save_json,
    validate_suite, main,
)
from drawtemp.sdk.r40_starters import create_starter_pair
from sporebound.game_session import GameSession

SHA = "a" * 40


def fixture():
    content, project = create_starter_pair("r40-adventure")
    good = capture_case(
        content, project, identifier="village", starter="r40-adventure",
        revision=SHA, steps=[
            {"operation": "route_realtime_step", "args": [1, 0],
             "expect": [{"path": ["scene_route", "current"],
                         "equals": "arrival"}]},
            {"operation": "route_realtime_step", "args": [0, 0],
             "expect": [{"path": ["mode"], "equals": "campaign"}]},
        ], links=[
            {"step": 1, "resource": ["project", "", "project"]},
        ],
    )
    failed = deepcopy(good)
    failed["scenario"]["id"] = "regression"
    failed["scenario"]["steps"][1]["expect"][0]["equals"] = "battle"
    return content, project, build_suite([good, failed])


class QALabHeadlessTests(unittest.TestCase):
    def test_bounded_batch_keeps_real_engine_and_reports_failure(self):
        content, project, suite = fixture()
        baseline = deepcopy(GameSession.new(
            content, project, "main", seed=17).recording())
        before = deepcopy(suite)
        report = run_batch(suite, content, project, revision=SHA)
        self.assertEqual(report["kind"], "drawtemp-r56b-batch-report")
        self.assertEqual(report["status"], "no-go")
        self.assertEqual(report["counts"], {"passed": 1, "failed": 1, "blocked": 0})
        self.assertFalse(report["release_certified"])
        self.assertFalse(report["revision_independently_attested"])
        self.assertEqual(report["cases"][0]["report"]["trace"][-1]["step"], 2)
        self.assertEqual(suite, before)
        self.assertEqual(
            GameSession.new(content, project, "main", seed=17).recording(),
            baseline)

    def test_examine_first_failure_and_navigate_typed_resource(self):
        content, project, suite = fixture()
        result = run_batch(suite, content, project, revision=SHA)
        passing = inspect_case(
            result["cases"][0]["report"], suite["cases"][0], 1)
        self.assertTrue(passing["reproduced_through_step"])
        self.assertEqual(passing["resource"], ["project", "", "project"])
        self.assertEqual(passing["trace"]["operation"], "route_realtime_step")
        failure = inspect_case(
            result["cases"][1]["report"], suite["cases"][1], 2)
        self.assertEqual(failure["failure"]["category"], "invariant")
        self.assertEqual(failure["failure"]["step"], 2)
        self.assertFalse(failure["reproduced_through_step"])
        self.assertIsNone(failure["resource"])
        with self.assertRaises(ValueError):
            inspect_case(result["cases"][0]["report"], suite["cases"][1], 1)
        with self.assertRaises(ValueError):
            inspect_case(result["cases"][1]["report"], suite["cases"][1], True)

    def test_selected_point_replays_actual_invariant_value(self):
        content, project, suite = fixture()
        batch = run_batch(suite, content, project, revision=SHA)
        passing = replay_to_step(
            suite["cases"][0], content, project, revision=SHA, step=1,
            report=batch["cases"][0]["report"])
        self.assertEqual(passing["status"], "reproduced")
        self.assertTrue(passing["observations"][0]["matches"])
        self.assertEqual(passing["observations"][0]["actual"], "arrival")
        failure = replay_to_step(
            suite["cases"][1], content, project, revision=SHA, step=2,
            report=batch["cases"][1]["report"])
        self.assertEqual(failure["status"], "invariant-failed")
        self.assertEqual(failure["observations"][0]["expected"], "battle")
        self.assertEqual(failure["observations"][0]["actual"], "campaign")
        self.assertFalse(failure["observations"][0]["matches"])
        self.assertFalse(failure["release_certified"])
        with self.assertRaises(ValueError):
            replay_to_step(suite["cases"][0], content, project,
                           revision="b" * 40, step=1)
        with self.assertRaises(ValueError):
            replay_to_step(suite["cases"][0], content, project,
                           revision=SHA, step=257)

    def test_stale_revision_blocks_all_scenarios(self):
        content, project, suite = fixture()
        report = run_batch(suite, content, project, revision="b" * 40)
        self.assertEqual(report["counts"], {"passed": 0, "failed": 0, "blocked": 2})
        self.assertEqual(report["status"], "no-go")
        self.assertEqual(report["cases"][0]["report"]["steps_executed"], 0)

    def test_qa_diff_detects_hash_and_status_changes(self):
        content, project, suite = fixture()
        before = run_batch(suite, content, project, revision=SHA)
        after = deepcopy(before)
        self.assertTrue(diff_batches(before, after)["equal"])
        after["cases"][0]["report"]["trace"][1]["digest"] = "0" * 64
        delta = diff_batches(before, after)
        self.assertFalse(delta["equal"])
        self.assertEqual(delta["changes"][0]["step_diffs"][0]["step"], 1)
        self.assertEqual(delta["changes"][0]["scenario"], "village")
        with self.assertRaises(ValueError):
            diff_batches(before, {**after, "suite_sha256": "0" * 64})

    def test_import_export_and_never_overwrite_source(self):
        content, project, suite = fixture()
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "suite.json"
            reportfile = root / "report.json"
            save_json(source, suite)
            self.assertEqual(read_suite(source), suite)
            with self.assertRaises(ValueError):
                save_json(source, suite, forbidden=[source])
            report = run_batch(suite, content, project, revision=SHA)
            save_json(reportfile, report, forbidden=[source])
            self.assertEqual(read_report(reportfile)["counts"]["failed"], 1)
            source.write_text('{"kind":"x","kind":"x"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                read_suite(source)
            source.write_text('{"kind":NaN}', encoding="utf-8")
            with self.assertRaises(ValueError):
                read_suite(source)

    def test_cli_outputs_identical_batch_and_refuses_source_overwrite(self):
        content, project, suite = fixture()
        clean = build_suite([suite["cases"][0]])
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "suite.json"
            output = root / "out.json"
            save_json(source, clean)
            result = main(["--suite", str(source), "--revision", SHA,
                           "--report", str(output)])
            self.assertEqual(result, 0)
            cli = read_report(output)
            api = run_batch(clean, content, project, revision=SHA)
            self.assertEqual(cli, api)
            self.assertEqual(main(["--suite", str(source), "--revision", SHA,
                                   "--report", str(source)]), 2)
            self.assertEqual(main(["--suite", str(source), "--revision",
                                   "b" * 40]), 2)

    def test_invalid_links_duplicates_and_oversized_batches_fail_closed(self):
        _, _, suite = fixture()
        self.assertEqual(suite["kind"], KIND)
        invalid = deepcopy(suite)
        invalid["cases"][0]["links"] += [
            {"step": 1, "resource": ["maps", "", "foo"]}]
        with self.assertRaises(ValueError):
            validate_suite(invalid)
        invalid = deepcopy(suite)
        invalid["cases"][0]["links"] = [
            {"step": True, "resource": ["project", "", "project"]}]
        with self.assertRaises(ValueError):
            validate_suite(invalid)
        invalid = deepcopy(suite)
        invalid["cases"][0]["links"][0]["resource"] = ["scenes", "bad", "node"]
        with self.assertRaises(ValueError):
            validate_suite(invalid)
        invalid = deepcopy(suite)
        invalid["cases"][1]["scenario"]["id"] = "village"
        with self.assertRaises(ValueError):
            validate_suite(invalid)
        with self.assertRaises(ValueError):
            build_suite([deepcopy(suite["cases"][0])] * 13)
        invalid = deepcopy(suite)
        invalid["schema"] = True
        with self.assertRaises(ValueError):
            validate_suite(invalid)


if __name__ == "__main__":
    unittest.main()
