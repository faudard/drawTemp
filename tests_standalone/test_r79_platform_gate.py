"""Headless R79 evidence contract tests: never run GPU or assert platform support."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from r79_platform_gate import evaluate, main  # noqa: E402

REVISION = "a" * 40


class R79GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def evidence(self, platform="linux", **patch):
        path = self.root / f"{platform}.log"
        path.write_text("R79 synthetic fixture (NOT hardware evidence)", encoding="utf-8")
        backend = {"linux": "vulkan", "windows": "d3d11", "macos": "metal"}[platform]
        data = {
            "schema": 1, "candidate": "qtquick-rhi-adaptive", "revision": REVISION,
            "platform": platform, "renderer_backend": backend, "physical_device": True,
            "device_id": f"test-{platform}", "os_version": "fixture", "qt_version": "6.8.3",
            "driver_version": "fixture", "maintenance_hours_per_quarter": 20,
            "cost_basis": "synthetic-only; no independent review",
            "benchmarks": {"frame_ms": [15.0] * 30, "cold_start_ms": 900, "peak_memory_mib": 256},
            "checks": {k: True for k in ("picking", "studio_player_parity", "save_replay", "input", "packaging", "license_review", "rollback")},
            "artifacts": [{"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}],
        }
        data.update(patch)
        manifest = self.root / f"{platform}.json"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        return manifest

    def report(self):
        return evaluate("qtquick-rhi-adaptive", REVISION, self.root)

    def test_empty_is_no_go(self):
        report = self.report()
        self.assertEqual(report["decision"], "NO-GO")
        self.assertEqual(report["required_platforms"], ["linux", "macos", "windows"])
        self.assertFalse(report["review_ready"])

    def test_complete_still_never_auto_approves(self):
        for platform in ("linux", "windows", "macos"):
            self.evidence(platform)
        report = self.report()
        self.assertTrue(report["review_ready"])
        self.assertEqual(report["decision"], "NO-GO")
        self.assertFalse(report["release_certified"])
        self.assertEqual(report["observations"][0]["frame_ms_p99"], 15)

    def test_emulator_and_failed_check_refused(self):
        self.evidence("linux", physical_device=False)
        self.assertIn("physical", str(self.report()["findings"]))
        self.evidence("linux", checks={"picking": False})
        self.assertIn("checks", str(self.report()["findings"]))

    def test_revision_and_nonfinite_refused(self):
        self.evidence("linux", revision="b" * 40)
        self.assertIn("mismatch", str(self.report()["findings"]))
        self.evidence("linux", benchmarks={"frame_ms": [float("nan")] * 30, "cold_start_ms": 1, "peak_memory_mib": 1})
        self.assertIn("non-finite", str(self.report()["findings"]))

    def test_artifact_corruption_and_escape_refused(self):
        self.evidence("linux")
        (self.root / "linux.log").write_text("tampered", encoding="utf-8")
        self.assertIn("mismatch", str(self.report()["findings"]))
        self.evidence("linux", artifacts=[{"path": "../escape", "sha256": "0" * 64}])
        self.assertIn("simple filename", str(self.report()["findings"]))

    def test_duplicate_platform_fails_closed(self):
        self.evidence("linux")
        (self.root / "copy.json").write_bytes((self.root / "linux.json").read_bytes())
        self.assertFalse(self.report()["review_ready"])
        self.assertIn("duplicate", str(self.report()["findings"]))

    def test_unknown_fields_and_backend_fail(self):
        self.evidence("linux", renderer_backend="metal")
        self.assertIn("backend", str(self.report()["findings"]))
        self.evidence("linux", unexpected=True)
        self.assertIn("fields", str(self.report()["findings"]))

    def test_symlink_refused(self):
        self.evidence("linux")
        link = self.root / "other.json"
        try:
            link.symlink_to(self.root / "linux.json")
        except (OSError, NotImplementedError):
            self.skipTest("symlink unavailable")
        self.assertIn("symlink", str(self.report()["findings"]))

    def test_cli_strict_signal_not_release(self):
        output = self.root / "report.json"
        rc = main(["--candidate", "qtquick-rhi-adaptive", "--revision", REVISION,
                   "--evidence-root", str(self.root / "not-here"), "--output", str(output),
                   "--require-review-ready"])
        self.assertEqual(rc, 1)
        self.assertEqual(json.loads(output.read_text())["decision"], "NO-GO")


if __name__ == "__main__":
    unittest.main()
