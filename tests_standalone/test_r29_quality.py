"""R29.A QA report, integrity, matrix and NO-GO release regressions."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.quality.r29 import (
    CHECKS, MODES, P0, PROBES, aggregate_matrix, create_report,
    verify_report, write_json,
)
from scripts.certify_multigenre_r29 import main, _probe, SUITES


REV = "a" * 40


class R29EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def fixture(self, runner="Linux", revision=REV, failed=()):
        folder = self.root / runner
        folder.mkdir(parents=True, exist_ok=True)
        probes = {}
        for name in PROBES:
            path = folder / (name + ".log")
            path.write_text(f"Executed {name} at SHA {revision}\n", encoding="utf-8")
            probes[name] = {
                "status": "fail" if name in failed else "pass",
                "exit_code": 1 if name in failed else 0,
                "command": ["python", "-m", "unittest", "test_placeholder"],
                "log": path.name,
                "sha256": sha256(path.read_bytes()).hexdigest(),
            }
        report = create_report(probes, revision=revision, runner=runner)
        write_json(folder / "r29-report.json", report)
        return folder / "r29-report.json", report

    def test_successful_bounded_probes_never_certify_unimplemented_modes(self):
        path, report = self.fixture()
        self.assertEqual(set(report["checks"]), set(CHECKS))
        self.assertEqual(set(report["modes"]), set(MODES))
        self.assertEqual(report["checks"]["R29.1"]["status"], "partial")
        self.assertEqual(report["checks"]["R29.7"]["status"], "blocked")
        self.assertEqual(report["modes"]["tactical_ct"]["status"], "partial")
        self.assertEqual(report["modes"]["action_realtime"]["status"], "blocked")
        self.assertEqual(report["modes"]["rpg_turn"]["status"], "blocked")
        self.assertIn("R29.10", P0)
        self.assertEqual(report["decision"], "no-go")
        self.assertFalse(verify_report(report, path.parent))
        with self.assertRaisesRegex(ValueError, "NO-GO"):
            verify_report(report, path.parent, require_release=True)

    def test_failed_probe_is_fail_and_cannot_be_greenwashed(self):
        path, report = self.fixture(failed=("tactical_replay",))
        self.assertEqual(report["checks"]["R29.1"]["status"], "fail")
        self.assertEqual(report["modes"]["tactical_ct"]["status"], "fail")
        self.assertFalse(verify_report(report, path.parent))
        forged = deepcopy(report)
        forged["checks"]["R29.1"]["status"] = "pass"
        forged["release_ready"] = True
        forged["decision"] = "go"
        with self.assertRaisesRegex(ValueError, "modified"):
            verify_report(forged, path.parent)

    def test_log_tampering_missing_and_escape_fail_closed(self):
        path, report = self.fixture()
        log = path.parent / "tactical_replay.log"
        log.write_text("corrupted bytes", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "integrity"):
            verify_report(report, path.parent)
        _, report = self.fixture()
        forged = deepcopy(report)
        forged["probes"]["visual_contract"]["log"] = "../unexpected.log"
        with self.assertRaisesRegex(ValueError, "unsafe log"):
            verify_report(forged, path.parent)
        (path.parent / "asset_contract.log").unlink()
        with self.assertRaises((ValueError, OSError)):
            verify_report(report, path.parent)

    def test_nonzero_exit_pass_and_missing_probes_rejected(self):
        path, report = self.fixture()
        forged = deepcopy(report)
        forged["probes"]["export_contract"]["exit_code"] = 3
        with self.assertRaisesRegex(ValueError, "exit code"):
            verify_report(forged, path.parent)
        forged = deepcopy(report)
        del forged["probes"]["asset_contract"]
        with self.assertRaisesRegex(ValueError, "incomplete"):
            verify_report(forged, path.parent)
        with self.assertRaisesRegex(ValueError, "every declared"):
            create_report({}, revision=REV, runner="Linux")

    def test_three_os_matrix_is_sha_bound_but_is_still_no_go(self):
        sources = [self.fixture(runner=name) for name in ("Linux", "Windows", "macOS")]
        result = aggregate_matrix(sources, expected_revision=REV)
        self.assertEqual(result["runners"], ["Linux", "Windows", "macOS"])
        self.assertTrue(result["matrix_verified"], result["errors"])
        self.assertFalse(result["release_ready"])
        self.assertEqual(result["decision"], "no-go")
        mixed = [sources[0], sources[1], self.fixture("macOS", "b" * 40)]
        bad = aggregate_matrix(mixed, expected_revision=REV)
        self.assertFalse(bad["matrix_verified"])
        self.assertTrue(any("same source SHA" in issue for issue in bad["errors"]))
        duplicate = aggregate_matrix([sources[0], sources[0], sources[2]])
        self.assertFalse(duplicate["matrix_verified"])
        self.assertTrue(any("Duplicate runner" in issue for issue in duplicate["errors"]))
        missing = aggregate_matrix(sources[:2])
        self.assertIn("Missing runners: macOS", missing["errors"])
        failed = list(sources)
        failed[0] = self.fixture("Linux", REV, failed=("save_recovery",))
        self.assertFalse(aggregate_matrix(failed)["matrix_verified"])

    def test_matrix_requires_real_immutable_revision(self):
        sources = [self.fixture(runner=name, revision="local")
                   for name in ("Linux", "Windows", "macOS")]
        matrix = aggregate_matrix(sources)
        self.assertFalse(matrix["matrix_verified"])
        self.assertTrue(any("40-hex" in error for error in matrix["errors"]))

    def test_cli_aggregation_and_require_release_exit_codes(self):
        for runner in ("Linux", "macOS", "Windows"):
            self.fixture(runner=runner)
        combined = self.root / "summary.json"
        with patch.dict("os.environ", {"GITHUB_SHA": REV}):
            self.assertEqual(main(["--aggregate", str(self.root),
                                   "--report", str(combined)]), 0)
            self.assertEqual(main(["--aggregate", str(self.root),
                                   "--report", str(combined),
                                   "--require-release"]), 2)
        data = json.loads(combined.read_text(encoding="utf-8"))
        self.assertTrue(data["matrix_verified"])
        self.assertFalse(data["release_ready"])

    def test_cli_probe_executes_only_allowlisted_unittest_targets(self):
        self.assertEqual(set(SUITES), set(PROBES))
        class Completed:
            returncode = 0
            stdout = "1 test OK"
        with patch("scripts.certify_multigenre_r29.subprocess.run",
                   return_value=Completed()) as run:
            result = _probe("tactical_replay", self.root)
        command = run.call_args.args[0]
        self.assertEqual(command[1:3], ["-m", "unittest"])
        self.assertTrue(all(name.startswith("tests_standalone.")
                            for name in command[3:-1]))
        self.assertEqual(result["status"], "pass")
        self.assertTrue((self.root / "tactical_replay.log").is_file())


if __name__ == "__main__":
    unittest.main()
