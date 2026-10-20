"""Headless R79.B contracts; never starts Qt nor certifies hardware."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from r79_rhi_spike import BACKENDS, normalize_observation, run_spike, validate

REV = "b" * 40


class R79RhiSpikeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    @staticmethod
    def observation(backend="opengl", **fields):
        obj = {
            "schema": 1, "requested_backend": backend, "observed_backend": backend,
            "projection": "isometric", "qt_version": "6.8.3", "qpa_platform": "xcb",
            "qml_ready": True, "scenegraph_initialized": True, "first_frame_observed": True,
            "picking_centres_passed": True, "picking_samples": 3,
            "capture_saved": True,
            "capture_sha256": hashlib.sha256(b"synthetic unit-test capture").hexdigest(),
            "error": "",
        }
        obj.update(fields)
        return obj

    def runner(self, observation=None, *, returncode=0, capture=True):
        def call(argv, **kwargs):
            self.assertEqual(kwargs["env"].get("QSG_RHI_BACKEND"), None)
            self.assertEqual(kwargs["env"].get("QT_QUICK_BACKEND"), None)
            self.assertEqual(argv[argv.index("--backend") + 1], "opengl")
            if capture:
                Path(argv[argv.index("--capture-path") + 1]).write_bytes(
                    b"synthetic unit-test capture")
            return subprocess.CompletedProcess(
                argv, returncode, json.dumps(observation or self.observation()), "")
        return call

    def run_case(self, label, **kwargs):
        args = {
            "backend": "opengl", "projection": "isometric", "revision": REV,
            "output_dir": self.root / label, "os_name": "linux",
            "runner": self.runner(),
        }
        args.update(kwargs)
        with patch.dict(os.environ, {
            "QSG_RHI_BACKEND": "vulkan", "QT_QUICK_BACKEND": "software"
        }):
            return run_spike(**args)

    def test_valid_synthetic_observation_never_go(self):
        result = self.run_case("valid")
        self.assertEqual(result["status"], "observed")
        self.assertEqual(result["decision"], "NO-GO")
        self.assertFalse(result["release_certified"])
        self.assertFalse(result["eligible_for_r79c"])
        self.assertFalse(result["physical_gpu_verified"])
        self.assertTrue((self.root / "valid/spike-result.json").is_file())

    def test_explicit_os_backend_matrix(self):
        self.assertIn("d3d11", BACKENDS["windows"])
        self.assertNotIn("d3d11", BACKENDS["linux"])
        for backend, projection, revision, os_name in (
            ("d3d11", "isometric", REV, "linux"),
            ("vulkan", "isometric", REV, "macos"),
            ("opengl", "side", REV, "linux"),
            ("opengl", "isometric", "../rev", "linux"),
        ):
            self.assertRaises(ValueError, validate, backend, projection, revision, os_name)

    def test_timeout_bounds_and_no_overwrite(self):
        self.assertRaises(ValueError, self.run_case, "invalid-ms", timeout_ms=999)
        (self.root / "exists").mkdir()
        self.assertRaises(ValueError, self.run_case, "exists")

    def test_backend_fallback_is_failure(self):
        obj = self.observation(observed_backend="software")
        result = self.run_case("fallback", runner=self.runner(obj))
        self.assertEqual(result["status"], "inconclusive")
        self.assertIn("fallback", str(result["findings"]))

    def test_unready_qml_is_failure(self):
        obj = self.observation(qml_ready=False, error="fixture QML error")
        result = self.run_case("qml", runner=self.runner(obj))
        self.assertEqual(result["status"], "inconclusive")
        self.assertIn("fixture QML error", str(result["findings"]))

    def test_missing_frame_and_failed_picking(self):
        obj = self.observation(first_frame_observed=False)
        self.assertEqual(self.run_case("frame", runner=self.runner(obj))["status"], "inconclusive")
        obj = self.observation(picking_samples=2)
        self.assertEqual(self.run_case("pick", runner=self.runner(obj))["status"], "inconclusive")

    def test_missing_capture_rejected(self):
        result = self.run_case("missing", runner=self.runner(capture=False))
        self.assertEqual(result["status"], "inconclusive")
        self.assertIn("screenshot", str(result["findings"]))

    def test_crash_and_timeout_fail_closed(self):
        result = self.run_case("crash", runner=self.runner(returncode=6))
        self.assertIn("exited with code 6", str(result["findings"]))
        def hanging(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        result = self.run_case("hang", runner=hanging)
        self.assertIn("timed out", str(result["findings"]))

    def test_malformed_child_data_is_rejected(self):
        result = self.run_case("schema", runner=self.runner({"schema": 2}))
        self.assertIn("invalid child evidence", str(result["findings"]))
        with self.assertRaises(ValueError):
            normalize_observation(
                self.observation(capture_sha256="0"), "opengl", "isometric")

    def test_offscreen_requires_explicit_opt_in(self):
        with patch.dict(os.environ, {"QT_QPA_PLATFORM": "offscreen"}):
            result = self.run_case("headless")
        self.assertEqual(result["status"], "inconclusive")
        self.assertIn("headless QPA", str(result["findings"]))
        self.assertTrue((self.root / "headless/spike-result.json").exists())

    def test_failure_does_not_retry_or_change_pc_player(self):
        calls = []
        def failure(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 1, "", "Qt refused backend")
        result = self.run_case("fail", runner=failure)
        self.assertEqual(len(calls), 1)
        self.assertIn("Qt refused backend", result["child_stderr_excerpt"])
        self.assertFalse(result["changes_player_defaults"])


if __name__ == "__main__":
    unittest.main()
