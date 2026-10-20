"""R40.B: mandatory headless source evidence with fail-closed release decision."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from drawtemp.core import GameSession
from drawtemp.quality.r40_headless import (
    BLOCKERS, _PROBES, audit_r40_source, main,
)
from drawtemp.sdk.r40_starters import STARTER_KINDS, create_starter_pair
from sporebound.model import RuleError


class R40HeadlessTests(unittest.TestCase):
    def test_four_real_authoritative_routes_with_disk_resume(self):
        report = audit_r40_source()
        self.assertEqual(report["kind"], "drawtemp-r40-source-audit")
        self.assertTrue(report["source_checks_passed"], report["probes"])
        self.assertEqual(len(report["probes"]), 4)
        self.assertEqual({row["starter"] for row in report["probes"]},
                         set(STARTER_KINDS))
        self.assertTrue(all(row["checkpoints"] > 0
                            for row in report["probes"]))
        self.assertEqual(report["decision"], "NO-GO")
        self.assertFalse(report["release_ready"])
        self.assertEqual(report["missing_release_evidence"], list(BLOCKERS))

    def test_an_uncertified_source_probe_cannot_be_recorded_as_green(self):
        def failing(*_args):
            raise RuleError("Injected failure in authentic runtime")
        patched = dict(_PROBES)
        patched["r40-adventure"] = (failing, "Injected failure")
        with patch.dict(_PROBES, patched, clear=True):
            report = audit_r40_source()
        self.assertFalse(report["source_checks_passed"])
        self.assertFalse(report["release_ready"])
        failure = next(row for row in report["probes"]
                       if row["starter"] == "r40-adventure")
        self.assertFalse(failure["passed"])
        self.assertIn("Injected failure", failure["error"])

    def test_rejected_waystone_gate_cannot_mutate_campaign(self):
        for kind in ("r40-adventure", "r40-metroidvania"):
            with self.subTest(starter=kind):
                content, project = create_starter_pair(kind)
                session = GameSession.new(content, project, "main", seed=17)
                before = deepcopy(session.recording())
                with self.assertRaises(RuleError):
                    session.route_transition("to_ruins")
                with self.assertRaises(RuleError):
                    session.route_transition("to_citadel")
                self.assertEqual(session.recording(), before)

    def test_route_save_checkpoint_rejects_invalid_history(self):
        content, project = create_starter_pair("r40-adventure")
        session = GameSession.new(content, project, "main", seed=17)
        for _ in range(4):
            session.route_realtime_step(1, 0)
        session.route_interact("waystone")
        session.route_transition("to_ruins")
        document = session.recording()
        invalid = deepcopy(document)
        invalid["scene_route"]["history"] = ["to_citadel"]
        from sporebound.game_session import digest
        invalid["digest"] = digest({key: value for key, value
                                    in invalid.items() if key != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(invalid, content, project)
        self.assertEqual(
            GameSession.from_recording(document, content, project).recording(),
            document)

    def test_cli_writes_report_and_fail_closed_release_exit_code(self):
        with TemporaryDirectory() as root:
            output = Path(root) / "reports" / "r40.json"
            self.assertEqual(main(["--report", str(output)]), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["source_checks_passed"])
            self.assertFalse(report["release_ready"])
            self.assertEqual(main(["--report", str(output),
                                   "--require-release"]), 2)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["decision"], "NO-GO")
            self.assertEqual(len(report["probes"]), 4)


if __name__ == "__main__":
    unittest.main()
