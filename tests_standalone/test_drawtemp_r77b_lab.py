"""R77.B verified headless lab: no forged coverage, explicit human reviews."""
from copy import deepcopy
import unittest

from drawtemp.quality.r77_exploratory import explore_action_scene
from drawtemp.quality.r77_lab import (
    build_lab_view, compare_lab_views, minimize_runtime_failure, triage_finding,
)


def make_scene(*, gate=False):
    return {
        "id": "lab_scene", "width": 5, "height": 5,
        "walls": [[2, y] for y in (0, 1, 3, 4)] if gate else [],
        "hero": {"pos": [1, 2], "hp": 20}, "enemies": [],
        "objects": ([{"id": "gate", "kind": "door", "pos": [2, 2],
                      "item": "", "requires": "key"}] if gate else []),
    }


def run(scene, *, seeds=(1,), ticks=16):
    return explore_action_scene(scene, [[3, 2]], seeds=seeds,
                                ticks_per_seed=ticks, state_budget=5000)


class ExplorationLabHeadlessTests(unittest.TestCase):
    def test_heatmap_reconstructs_actual_positions_and_seed_timelines(self):
        scene = make_scene()
        before = deepcopy(scene)
        report = run(scene, seeds=(1, 3), ticks=24)
        saved = deepcopy(report)
        view = build_lab_view(scene, report)
        self.assertEqual(scene, before)
        self.assertEqual(report, saved)
        self.assertTrue(view["source_verified"])
        self.assertFalse(view["release_certified"])
        self.assertEqual(view["scene_sha256"], report["scene_sha256"])
        self.assertEqual(view["coverage"]["goals"], report["coverage"]["goals"])
        self.assertEqual([row["seed"] for row in view["runs"]], [1, 3])
        ticks = sum(run["ticks"] + 1 for run in view["runs"])
        self.assertEqual(sum(row["visits"] for row in view["heatmap"]), ticks)
        self.assertTrue(any(row["cell"] == [1, 2] and row["visits"] >= 2
                            for row in view["heatmap"]))
        for item in view["runs"]:
            self.assertEqual(len(item["timeline"]), item["ticks"] + 1)
            self.assertEqual(item["timeline"][0]["tick"], 0)
            self.assertEqual(item["timeline"][-1]["tick"], item["ticks"])

    def test_tampered_report_and_wrong_scene_rejected(self):
        scene = make_scene()
        report = run(scene)
        altered = deepcopy(report)
        altered["runs"][0]["ticks"] = 999
        with self.assertRaises(ValueError):
            build_lab_view(scene, altered)
        modified = deepcopy(scene)
        modified["walls"].append([3, 2])
        with self.assertRaises(ValueError):
            build_lab_view(modified, report)
        changed = deepcopy(report)
        changed["release_certified"] = True
        with self.assertRaises(ValueError):
            build_lab_view(scene, changed)
        missing = deepcopy(report)
        del missing["config"]["goals"]
        with self.assertRaises(ValueError):
            build_lab_view(scene, missing)

    def test_static_softlock_witness_and_explicit_triage(self):
        scene = make_scene(gate=True)
        before = deepcopy(scene)
        report = run(scene, ticks=12)
        view = build_lab_view(scene, report)
        self.assertEqual(view["status"], "abstract_softlock_risk")
        self.assertTrue(view["findings"])
        self.assertIn("static:", view["findings"][0]["id"])
        notes = triage_finding(
            view, view["findings"][0]["id"], "suspected_false_positive",
            "Le Player traverse la porte dans le test manuel.")
        self.assertTrue(notes[view["findings"][0]["id"]]["human_review_only"])
        self.assertEqual(scene, before)
        self.assertNotIn("annotations", report)
        with self.assertRaises(ValueError):
            triage_finding(view, "nonexistent", "needs_investigation", "Long note")
        with self.assertRaises(ValueError):
            triage_finding(view, view["findings"][0]["id"],
                           "certified", "Long note")

    def test_comparison_is_delta_not_certification(self):
        scene = make_scene()
        old = build_lab_view(scene, run(scene, seeds=(2,), ticks=4))
        newer = build_lab_view(scene, run(scene, seeds=(2,), ticks=48))
        comparison = compare_lab_views(old, newer)
        self.assertFalse(comparison["source_changed"])
        self.assertFalse(comparison["release_certified"])
        self.assertTrue(comparison["visits_delta"])
        same_id_other_layout = make_scene()
        same_id_other_layout["walls"] = [[4, 4]]
        new_scene = build_lab_view(
            same_id_other_layout, run(same_id_other_layout, seeds=(2,), ticks=4))
        self.assertTrue(compare_lab_views(old, new_scene)["source_changed"])
        another = deepcopy(newer)
        another["scene"] = "unrelated"
        with self.assertRaises(ValueError):
            compare_lab_views(old, another)

    def test_real_rule_exception_reproducer_reduced(self):
        scene = make_scene()
        prefix = [{"tick": n, "dx": 0} for n in range(1, 7)]
        failing = {"tick": 7, "interact": "no_such_object"}
        result = minimize_runtime_failure(
            scene, prefix, failing, error_type="ActionError",
            message="Unknown interaction object")
        self.assertEqual(result["status"], "reproduced_reduced")
        self.assertEqual(len(result["commands"]), 1)
        self.assertEqual(result["commands"][0]["tick"], 1)
        self.assertEqual(result["commands"][0]["interact"], "no_such_object")
        self.assertFalse(result["release_certified"])
        unproven = minimize_runtime_failure(
            scene, prefix, failing, error_type="RuntimeError",
            message="not the actual exception")
        self.assertEqual(unproven["status"], "not_reproduced")
        for invalid in (0, True, 65):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                minimize_runtime_failure(
                    scene, prefix, failing, error_type="ActionError",
                    message="Unknown interaction object", max_replays=invalid)


if __name__ == "__main__":
    unittest.main()
