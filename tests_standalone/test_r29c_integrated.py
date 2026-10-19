"""R29.C fail-closed evidence plus conditional REAL R25.B/R26 integration tests."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r29c_integrated import (
    _trace, audit_action_disk, audit_route_disk, assemble_evidence,
)
from scripts.certify_r29c_journeys import main


def scene():
    return {"id": "r29c_real", "width": 8, "height": 8,
            "walls": [[4, 4]], "hero": {"pos": [1, 1], "hp": 12},
            "enemies": [], "objects": [
                {"id": "chest", "kind": "chest", "pos": [1, 2],
                 "item": "key", "requires": ""},
                {"id": "door", "kind": "door", "pos": [2, 1],
                 "item": "", "requires": "key"},
            ]}


class R29CHeadlessContracts(unittest.TestCase):
    def test_action_trace_requires_exact_monotonic_ticks_and_bounded_budget(self):
        for bad in ([], [{}], [{"tick": True}], [{"tick": 2}],
                    [{"tick": 1}, {"tick": 1}], ["tick"], [{"tick": 1}] * 2001):
            with self.subTest(bad=str(bad)[:60]), self.assertRaises(ValueError):
                _trace(bad)
        self.assertEqual(_trace([{"tick": 1, "dx": 1}]), [{"tick": 1, "dx": 1}])
        with self.assertRaises(ValueError):
            audit_action_disk(scene(), [{"tick": 1}], checkpoint_every=True)

    def test_route_command_allowlist_disallows_arbitrary_methods(self):
        for bad in ([], [{"op": "save", "args": ["file"]}],
                    [{"op": "__getattribute__", "args": ["secrets"]}],
                    [{"op": "route_move", "args": {}, "kw": {}}],
                    [{"op": "execute", "args": "not a list"}],
                    [{"op": [], "args": []}]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _trace(bad, route=True)
        accepted = [{"op": "route_transition", "args": ["to_arena"]}]
        self.assertEqual(_trace(accepted, route=True), accepted)
        self.assertIsNot(_trace(accepted, route=True), accepted)

    def test_unavailable_route_explicit_blocked_not_partial(self):
        class NotARouter:
            pass
        r = audit_route_disk(NotARouter(), [{"op": "route_move", "args": [1, 0]}])
        self.assertEqual(r["status"], "blocked")
        self.assertFalse(r["runtime_verified"])

    def test_evidence_requires_real_components_and_is_always_no_go(self):
        r = assemble_evidence()
        self.assertEqual(r["action"]["status"], "blocked")
        self.assertEqual(r["tactical_route"]["status"], "blocked")
        self.assertEqual(r["hybrid"]["status"], "blocked")
        self.assertFalse(r["release_ready"])
        self.assertEqual(r["decision"], "no-go")
        two_partials = assemble_evidence({"status": "partial"}, {"status": "partial"})
        self.assertFalse(two_partials["release_ready"])
        with self.assertRaises(ValueError):
            assemble_evidence({"status": "pass"})

    def test_cli_no_inputs_reports_blocked_and_release_guard_returns_two(self):
        with TemporaryDirectory() as root:
            report = Path(root) / "r29c.json"
            self.assertEqual(main(["--report", str(report)]), 0)
            output = json.loads(report.read_text(encoding="utf-8"))
            self.assertFalse(output["release_ready"])
            self.assertEqual(output["hybrid"]["status"], "blocked")
            self.assertEqual(main(["--report", str(report), "--require-action"]), 2)
            self.assertEqual(main(["--report", str(report), "--require-route"]), 2)
            self.assertEqual(main(["--report", str(report), "--require-release"]), 2)

    def test_cli_partial_option_sets_real_fail_not_missing_evidence(self):
        with TemporaryDirectory() as root:
            base = Path(root)
            path = base / "r29c.json"
            self.assertEqual(main(["--report", str(path), "--scene", str(base / "missing.json")]), 1)
            output = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(output["action"]["status"], "fail")
            self.assertFalse(output["release_ready"])

    def test_real_r26_action_tick_save_disk_replay_and_tamper(self):
        try:
            from sporebound.action_runtime import ActionRuntime
        except ImportError:
            self.skipTest("R26 #300 branch is not integrated here")
        original = scene()
        commands = [{"tick": 1, "interact": "chest"},
                    {"tick": 2, "interact": "chest"},
                    {"tick": 3, "interact": "door"},
                    {"tick": 4, "dx": 1}, {"tick": 5, "dx": 1},
                    {"tick": 6, "dy": 1}]
        before = deepcopy(commands)
        result = audit_action_disk(original, commands, checkpoint_every=2)
        self.assertEqual(result["status"], "partial")
        self.assertEqual([x["tick"] for x in result["checkpoints"]], [2, 4, 6])
        self.assertTrue(result["tamper_rejected"])
        self.assertEqual(commands, before)
        self.assertEqual(original, scene())
        baseline = ActionRuntime(scene())
        for command in commands:
            baseline.step(command)
        self.assertEqual(result["final_state_sha256"], baseline.digest())
        self.assertEqual(baseline.inventory.get("key"), 0)
        self.assertTrue(baseline.flags["opened:door"])
        self.assertFalse(result["release_certified"])

    def test_real_r25b_game_session_route_ct_and_disk_resume(self):
        try:
            from tests_standalone.test_r25_scene_router import scene_fixture
            from sporebound.game_session import GameSession
        except ImportError:
            self.skipTest("R25.B #314 SceneRouter tests not integrated here")
        content, project = scene_fixture()
        session = GameSession.new(content, project, "main", seed=17)
        session.progress.story_flags["portal_open"] = True
        session.progress.inventory["potion"] = 3
        session.progress.hero("jeanne").xp = 12
        commands = [
            {"op": "route_move", "args": [1, 0]},
            {"op": "route_transition", "args": ["to_arena"]},
            {"op": "execute", "args": [{"kind": "interact", "unit": "jeanne", "object": "lever"}]},
            {"op": "abandon_encounter", "args": []},
            {"op": "route_transition", "args": ["retreat"]},
        ]
        initial = session.recording()
        report = audit_route_disk(session, commands, checkpoint_every=2)
        self.assertEqual(report["status"], "partial")
        self.assertTrue(report["real_ct_route_verified"])
        self.assertEqual(report["visited_modes"][0], "campaign")
        self.assertIn("battle", report["visited_modes"])
        self.assertEqual(report["visited_modes"][-1], "campaign")
        self.assertEqual(len(report["checkpoints"]), 3)
        self.assertEqual(session.recording(), initial)
        self.assertFalse(report["release_certified"])


if __name__ == "__main__":
    unittest.main()
