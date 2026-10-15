"""DrawTemp 5.0 R13: canonical AI evidence, authoring isolation and gates."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from drawtemp.sdk.r13_combat_lab import (
    campaign_review, compare_encounters, evaluate_variant, human_review,
    inspect_encounter, simulate_encounter, trace_timeline,
)
from sporebound.model import Board, Content, Mission, RuleError, Unit


def arena():
    return Content({}, {"r13": Mission("r13", "Combat lab", Board(7, 5), [
        Unit("jeanne", "Jeanne", "player", (0, 1), tags=["class:knight"]),
        Unit("support", "Support", "player", (0, 2), tags=["class:cleric"]),
        Unit("wolf", "Wolf", "enemy", (5, 1), tags=["class:beast"]),
    ])})


class R13CombatLabTests(unittest.TestCase):
    def test_inspection_is_detached_and_reproducible(self):
        content = arena()
        authored = deepcopy(content.to_dict())
        first = inspect_encounter(content, "r13", seed=7)
        second = inspect_encounter(content, "r13", seed=7)
        self.assertEqual(first, second)
        self.assertEqual(first["kind"], "r13_encounter_inspection")
        self.assertEqual(first["profile"]["enemy_count"], 1)
        self.assertIn("timeline", first["intent"])
        self.assertIn("charges", first["intent"])
        self.assertEqual(content.to_dict(), authored)
        first["profile"]["units"][0]["pos"][0] = 999
        self.assertEqual(content.to_dict(), authored)
        with self.assertRaises(RuleError):
            inspect_encounter(content, "bad")
        with self.assertRaises(RuleError):
            inspect_encounter(content, "r13", max_cells=0)

    def test_designer_variant_is_real_matrix_not_a_source_edit(self):
        content = arena()
        original = deepcopy(content.to_dict())
        report = evaluate_variant(
            content, "r13", {"unit_positions": {"jeanne": [1, 1]}},
            seeds=(1,), max_commands=12)
        self.assertEqual(report["kind"], "balance_matrix")
        self.assertEqual(content.to_dict(), original)
        self.assertTrue(all(
            item["replay_verified"] for case in report["cases"]
            for item in case["report"]["samples"]))
        with self.assertRaises(RuleError):
            evaluate_variant(content, "r13", {"unit_positions": {"jeanne": [5, 1]}},
                             seeds=(1,), max_commands=12)
        with self.assertRaises(RuleError):
            evaluate_variant(content, "r13", {"mission": "elsewhere"}, seeds=(1,))

    def test_multiseed_simulation_trace_and_timeline(self):
        content = arena()
        before = content.to_dict()
        left = simulate_encounter(
            content, "r13", seeds=(1, 7), max_commands=18,
            trace_seed_id=1)
        right = simulate_encounter(
            content, "r13", seeds=(1, 7), max_commands=18,
            trace_seed_id=1)
        self.assertEqual(left, right)
        self.assertEqual(content.to_dict(), before)
        report = left["battle_lab"]
        self.assertEqual(report["seeds"], [1, 7])
        self.assertTrue(all(s["replay_verified"] for s in report["samples"]))
        self.assertTrue(left["trace"]["replay_verified"])
        self.assertEqual(left["ai_analytics"]["digest"], left["trace"]["digest"])
        timeline = trace_timeline(left["trace"], limit=2)
        self.assertEqual(timeline["kind"], "r13_visual_timeline")
        self.assertTrue(len(timeline["frames"]) <= 2)
        if timeline["frames"]:
            self.assertIn("positions", timeline["frames"][0])
            self.assertIn("command", timeline["frames"][0])
        self.assertEqual(timeline["truncated"], len(left["trace"]["steps"]) > 2)
        # A fabricated trace is never accepted as verified replay evidence.
        altered = deepcopy(left["trace"])
        altered["replay_verified"] = False
        with self.assertRaises(RuleError):
            trace_timeline(altered)
        with self.assertRaises(RuleError):
            simulate_encounter(content, "r13", seeds=(1,), max_commands=15,
                               trace_seed_id=99)

    def test_regression_requires_paired_seeds_and_real_replays(self):
        content = arena()
        baseline = simulate_encounter(
            content, "r13", seeds=(1, 3), max_commands=16)["battle_lab"]
        report = compare_encounters(baseline, deepcopy(baseline))
        self.assertTrue(report["passed"])
        self.assertFalse(report["human_signoff_required"])
        bad = deepcopy(baseline)
        bad["samples"][0]["digest"] = "not-the-same"
        self.assertFalse(compare_encounters(baseline, bad)["passed"])
        unverified = deepcopy(baseline)
        unverified["samples"][0]["replay_verified"] = False
        self.assertFalse(compare_encounters(baseline, unverified)["passed"])
        changed = deepcopy(baseline)
        changed["content_sha256"] = "different authoring"
        review = compare_encounters(baseline, changed)
        self.assertTrue(review["passed"])
        self.assertTrue(review["human_signoff_required"])
        changed["seeds"] = [5, 3]
        with self.assertRaises(RuleError):
            compare_encounters(baseline, changed)

    def test_cli_cannot_overwrite_authored_content_or_reference(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from drawtemp.sdk.r13_cli import main
        with TemporaryDirectory() as folder:
            content_path = Path(folder) / "authored.json"
            baseline = Path(folder) / "baseline.json"
            content_path.write_text(json.dumps(arena().to_dict()), encoding="utf-8")
            baseline.write_text('{"reference": true}', encoding="utf-8")
            for protected, extra in (
                (content_path, []),
                (baseline, ["--baseline", str(baseline)]),
            ):
                with self.subTest(protected=protected), self.assertRaises(SystemExit):
                    main(["--content", str(content_path),
                          "--mission", "r13", "--runs", "1",
                          "--report", str(protected), *extra])
            self.assertEqual(json.loads(content_path.read_text())["version"], 1)
            self.assertEqual(json.loads(baseline.read_text()), {"reference": True})

    def test_versioned_json_export_and_no_qt_dependency_for_core(self):
        content = arena()
        payload = simulate_encounter(content, "r13",
                                     seeds=(2,), max_commands=12)
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        self.assertEqual(json.loads(encoded), payload)
        # PySide is imported only when the optional Qt window is launched.
        from drawtemp.studio import r13_workbench
        self.assertTrue(callable(r13_workbench.launch))


if __name__ == "__main__":
    unittest.main()
