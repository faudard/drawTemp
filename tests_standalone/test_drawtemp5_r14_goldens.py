"""R14.5 regression tests: complete matrix, manual review, integrity and diff artifacts."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r14_goldens import (
    EXPECTED, MAX_CHANGED_FRACTION, approve_candidates, case_id,
    digest, evaluate_capture, html_report, load_approved, profile_id, write_json,
)

PROFILE = "linux-qt6.8.3-software"


def build_candidates(root):
    output = Path(root) / "candidate"
    rows = {}
    for target, dpi, zoom in EXPECTED:
        key = case_id(target, dpi, zoom)
        path = output / "actual" / (key + ".png")
        path.parent.mkdir(parents=True, exist_ok=True)
        # This suite tests manifest integrity, not Qt rendering or raster quality.
        path.write_bytes(("fixture image " + key).encode())
        rows[key] = {
            "target": target, "dpi": dpi, "zoom": zoom,
            "width": 12 * dpi, "height": 9 * dpi,
            "capture_status": "captured", "sha256": digest(path),
        }
    report = {
        "schema": 1, "profile": PROFILE, "os": "linux", "qt": "6.8.3",
        "revision": "a" * 40, "capture_complete": True, "cases": rows,
    }
    write_json(output / "r14-visual.json", report)
    return output, report


class GoldenManifestTests(unittest.TestCase):
    def test_exact_twelve_real_scene_variants(self):
        self.assertEqual(len(EXPECTED), 12)
        self.assertEqual(len({case_id(*case) for case in EXPECTED}), 12)
        self.assertEqual(case_id("player", 2, 0.75), "player-dpi2-zoom075")
        self.assertRaises(ValueError, case_id, "unknown", 1, 1.0)

    def test_pin_profile_and_missing_baseline_stay_blocked(self):
        self.assertEqual(profile_id("Linux", "6.8.3"), PROFILE)
        self.assertRaises(ValueError, profile_id, "Linux", "6.9.0")
        self.assertRaises(ValueError, profile_id, "Linux", "6.8.3", "opengl")
        with TemporaryDirectory() as folder:
            output, report = build_candidates(folder)
            evaluate_capture(output, Path(folder) / "goldens", report)
            self.assertFalse(report["goldens_reviewed"])
            self.assertEqual(report["comparison"], "blocked")
            self.assertFalse(report["release_certified"])
            self.assertTrue(all(r["comparison"] == "blocked"
                                for r in report["cases"].values()))
            html_report(output, report)
            page = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("player-dpi2-zoom075", page)
            self.assertIn("certification matérielle: NON", page)

    def test_manual_approval_requires_all_cases_and_named_reviewer(self):
        with TemporaryDirectory() as folder:
            output, report = build_candidates(folder)
            goldens = Path(folder) / "goldens"
            with self.assertRaises(ValueError):
                approve_candidates(output, goldens, reviewer="")
            report["cases"].pop(case_id(*EXPECTED[-1]))
            write_json(output / "r14-visual.json", report)
            with self.assertRaisesRegex(ValueError, "incomplete"):
                approve_candidates(output, goldens, reviewer="human")
            output, _ = build_candidates(folder)
            manifest = approve_candidates(output, goldens, reviewer="QA reviewer")
            approved = load_approved(goldens, PROFILE)
            self.assertTrue(approved["reviewed"])
            self.assertEqual(approved["reviewer"], "QA reviewer")
            self.assertEqual(len(approved["cases"]), 12)
            self.assertTrue(manifest.is_file())
            with self.assertRaisesRegex(ValueError, "Already reviewed"):
                approve_candidates(output, goldens, reviewer="QA reviewer")

    def test_mutation_and_traversal_in_approved_manifest_fail_closed(self):
        with TemporaryDirectory() as folder:
            output, _ = build_candidates(folder)
            goldens = Path(folder) / "goldens"
            manifest_path = approve_candidates(output, goldens, reviewer="reviewer")
            approved = json.loads(manifest_path.read_text(encoding="utf-8"))
            first = case_id(*EXPECTED[0])
            (manifest_path.parent / (first + ".png")).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                load_approved(goldens, PROFILE)
            approved["cases"][first]["filename"] = "../escape.png"
            write_json(manifest_path, approved)
            with self.assertRaisesRegex(ValueError, "Unsafe golden"):
                load_approved(goldens, PROFILE)

    def test_cannot_compare_unreviewed_manifest(self):
        with TemporaryDirectory() as folder:
            output, _ = build_candidates(folder)
            goldens = Path(folder) / "goldens"
            manifest = approve_candidates(output, goldens, reviewer="reviewer")
            data = json.loads(manifest.read_text("utf-8"))
            data["reviewed"] = False
            write_json(manifest, data)
            with self.assertRaisesRegex(ValueError, "unreviewed"):
                load_approved(goldens, PROFILE)


class PixelDiffRoundtripTests(unittest.TestCase):
    def test_all_twelve_pixel_diff_reports_and_thresholds(self):
        try:
            from PySide6.QtGui import QColor, QImage
        except ImportError:
            self.skipTest("PySide6 pinned in Qt CI")
        with TemporaryDirectory() as folder:
            output = Path(folder) / "candidate"
            report = {"schema": 1, "profile": PROFILE, "os": "linux",
                      "qt": "6.8.3", "capture_complete": True, "cases": {}}
            for target, dpi, zoom in EXPECTED:
                key = case_id(target, dpi, zoom)
                path = output / "actual" / (key + ".png")
                path.parent.mkdir(parents=True, exist_ok=True)
                frame = QImage(20 * dpi, 20 * dpi, QImage.Format_RGBA8888)
                frame.fill(QColor("#263c45"))
                self.assertTrue(frame.save(str(path), "PNG"))
                report["cases"][key] = {
                    "target": target, "dpi": dpi, "zoom": zoom,
                    "width": frame.width(), "height": frame.height(),
                    "capture_status": "captured", "sha256": digest(path),
                }
            write_json(output / "r14-visual.json", report)
            goldens = Path(folder) / "goldens"
            approve_candidates(output, goldens, reviewer="human")
            evaluate_capture(output, goldens, report)
            self.assertEqual(report["comparison"], "pass")
            self.assertTrue(all(r["metrics"]["changed_pixels"] == 0
                                for r in report["cases"].values()))
            # One changed pixel: strict 0.1% fraction means 1/400 = 0.25% fails.
            key = case_id("studio", 1, 1.0)
            path = output / "actual" / (key + ".png")
            image = QImage(str(path))
            image.setPixelColor(3, 3, QColor("#ff0000"))
            self.assertTrue(image.save(str(path), "PNG"))
            # The image is a new capture in the test: update its recorded digest
            # before asserting that the pixel comparator catches the regression.
            report["cases"][key]["sha256"] = digest(path)
            evaluate_capture(output, goldens, report)
            self.assertEqual(report["comparison"], "fail")
            self.assertEqual(report["cases"][key]["metrics"]["changed_pixels"], 1)
            self.assertGreater(report["cases"][key]["metrics"]["changed_fraction"],
                               MAX_CHANGED_FRACTION)
            self.assertTrue((output / "diff" / (key + ".png")).is_file())
            html_report(output, report)
            self.assertIn("Différence", (output / "index.html").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
