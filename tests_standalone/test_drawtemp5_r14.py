"""R14 regression tests: real contracts, and fail-closed certification evidence."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r14 import (
    ALL_CHECKS, P0_CHECKS, evidence_report, frame_metrics, percentile,
    safe_asset_path, validate_asset_manifest, validate_gpu_profile,
    verify_report, write_report,
)


class R14QualityTests(unittest.TestCase):
    def test_percentiles_are_ordered_and_reject_invalid_samples(self):
        result = frame_metrics([2, 3, 1, 4, 5])
        self.assertEqual(result["p50_ms"], 3.0)
        self.assertEqual(result["p95_ms"], 4.8)
        self.assertEqual(result["p99_ms"], 4.96)
        self.assertRaises(ValueError, percentile, [], 95)
        self.assertRaises(ValueError, percentile, [1, -1], 50)
        self.assertRaises(ValueError, percentile, [float("nan")], 50)
        self.assertRaises(ValueError, percentile, [1], 101)

    def test_gpu_evidence_requires_real_backend_and_complete_matrix(self):
        profile = {"schema": 1, "device": {
            "os": "Linux", "gpu": "reference-device", "driver": "reference-driver",
            "qt": "6.8.3", "backend": "vulkan", "software": False,
            "resolution": [1920, 1080]}, "scenes": [
                {"map_size": size, "zoom_px": zoom, "actors": 80,
                 "frame_times_ms": [16.0] * 120}
                for size in (32, 64, 128) for zoom in (24, 54, 96)
            ]}
        self.assertEqual(len(validate_gpu_profile(profile)["scenes"]), 9)
        profile["device"]["software"] = True
        with self.assertRaisesRegex(ValueError, "Real hardware"):
            validate_gpu_profile(profile)
        profile["device"]["software"] = False
        profile["scenes"].pop()
        with self.assertRaisesRegex(ValueError, "Missing size"):
            validate_gpu_profile(profile)
        profile["scenes"][-1]["frame_times_ms"] = [float("nan")] * 120
        with self.assertRaises(ValueError):
            validate_gpu_profile(profile)

    def test_asset_paths_hashes_and_duplicate_detection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "tiles.png"
            payload.write_bytes(b"PNG fixture")
            digest = hashlib.sha256(payload.read_bytes()).hexdigest()
            self.assertEqual(safe_asset_path(root, "tiles.png"), payload)
            self.assertEqual(validate_asset_manifest(root, [
                {"path": "tiles.png", "sha256": digest}]), [])
            for path in ("../tiles.png", "nested/../tiles.png", "/etc/passwd",
                         "C:/outside", "nested\\file", "./tiles.png", "a//b", ""):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    safe_asset_path(root, path)
            self.assertTrue(validate_asset_manifest(root, [
                {"path": "tiles.png", "sha256": "0" * 64}]))
            self.assertTrue(validate_asset_manifest(root, [
                {"path": "tiles.png", "sha256": digest},
                {"path": "tiles.png", "sha256": digest}]))
            outside = root.parent / (root.name + "-outside")
            outside.write_text("outside", encoding="utf-8")
            try:
                shortcut = root / "link"
                try:
                    shortcut.symlink_to(outside)
                except (OSError, NotImplementedError):
                    self.skipTest("Host forbids creating symlinks")
                with self.assertRaises(ValueError):
                    safe_asset_path(root, "link")
            finally:
                outside.unlink(missing_ok=True)

    def test_evidence_is_not_a_release_pass_without_all_p0(self):
        report = evidence_report({"R14.2": {"status": "pass", "detail": "Selected tests succeeded"}},
                                 revision="abc123")
        self.assertFalse(report["p0_certified"])
        self.assertEqual(report["checks"]["R14.6"]["status"], "blocked")
        self.assertFalse(verify_report(report))
        with self.assertRaisesRegex(ValueError, "incomplete"):
            verify_report(report, require_complete=True)
        complete = {key: {"status": "pass", "detail": "fixture evidence"} for key in P0_CHECKS}
        report = evidence_report(complete)
        self.assertTrue(verify_report(report, require_complete=True))
        report["p0_certified"] = False
        with self.assertRaisesRegex(ValueError, "mismatched"):
            verify_report(report)
        self.assertEqual(len(ALL_CHECKS), 12)

    def test_report_roundtrip_and_invalid_status_rejected(self):
        report = evidence_report({})
        with TemporaryDirectory() as directory:
            path = Path(directory) / "reports" / "r14.json"
            write_report(path, report)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["checks"],
                             report["checks"])
        with self.assertRaises(ValueError):
            evidence_report({"R14.1": {"status": "success", "detail": "no"}})


if __name__ == "__main__":
    unittest.main()
