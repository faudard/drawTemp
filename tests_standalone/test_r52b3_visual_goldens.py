"""R52.B3: golden matrix contracts, approval safety and Qt pixel comparator.

Pure tests do not manufacture approved screenshots or certify a GPU.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r52_goldens import (
    DPRS, EXPECTED, MODES, PHASES, TARGETS, approve_candidates, case_id,
    expected_world_anchors, fixture_scene, fingerprint, load_approved,
    profile_id, reference_projection, write_json,
)
from drawtemp.render.iso_scene import (Camera, IsoProjection,
                                       TopDownProjection, SideProjection, fingerprint as scene_fingerprint)
from drawtemp.render.depth_pipeline import world_to_screen, screen_to_world

ROOT = Path(__file__).resolve().parents[1]


class R52GoldenContracts(unittest.TestCase):
    def test_exact_36_case_coverage(self):
        self.assertEqual((len(MODES), len(DPRS), len(PHASES), len(TARGETS)), (3, 3, 2, 2))
        self.assertEqual(len(EXPECTED), 36)
        self.assertEqual(len({case_id(*row) for row in EXPECTED}), 36)
        self.assertEqual(case_id("studio", "side", 1.5, "night"),
                         "studio-side-dpi1p5-night")
        self.assertEqual(case_id("player", "isometric", 2, "day"),
                         "player-isometric-dpi2-day")
        for case in (("studio", "perspective", 1, "day"),
                     ("player", "side", 1.25, "day"),
                     ("viewer", "side", 1, "night"),
                     ("studio", "side", 2, "twilight")):
            with self.subTest(case=case), self.assertRaises(ValueError):
                case_id(*case)

    def test_three_frozen_world_projection_references(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.assertEqual(reference_projection(mode),
                                 expected_world_anchors()[mode])
        self.assertEqual(expected_world_anchors()["side"]["tile:4:3"], (256, 48))
        self.assertEqual(expected_world_anchors()["isometric"]["tile:4:3"], (48, 144))
        self.assertEqual(expected_world_anchors()["top_down"]["tile:4:3"], (256, 192))
        with self.assertRaises(ValueError):
            reference_projection("unknown")

    def test_dpi_changes_only_device_pixel_positions(self):
        scene = fixture_scene()
        source = scene_fingerprint(scene)
        self.assertEqual(len(scene["tiles"]), 36)
        anchors = {"isometric": IsoProjection(), "top_down": TopDownProjection(),
                   "side": SideProjection()}
        for mode, projection in anchors.items():
            camera = Camera(width=640, height=480, zoom=1.35, pan_x=47, pan_y=-31)
            for dpr in DPRS:
                with self.subTest(mode=mode, dpr=dpr):
                    sx, sy = world_to_screen(camera, projection, 4, 3, elevation=2)
                    self.assertEqual(screen_to_world(
                        camera, projection, sx, sy, elevation=2), (4.0, 3.0))
                    physical = sx * dpr, sy * dpr
                    self.assertAlmostEqual(physical[0] / dpr, sx)
                    self.assertAlmostEqual(physical[1] / dpr, sy)
                    self.assertEqual(scene_fingerprint(scene), source)

    def test_pinned_software_reference_profile(self):
        self.assertEqual(profile_id("Linux", "6.8.3"),
                         "linux-qt6.8.3-software")
        for os_name, version, backend in (
                ("Linux", "6.9.0", "software"),
                ("Linux", "6.8.3", "opengl"),
                ("FreeBSD", "6.8.3", "software")):
            with self.subTest(value=(os_name, version, backend)), self.assertRaises(ValueError):
                profile_id(os_name, version, backend)

    def test_review_manifest_missing_is_blocked_and_invalid_review_refused(self):
        with TemporaryDirectory() as folder:
            profile = profile_id("linux", "6.8.3")
            goldens = Path(folder) / "goldens"
            self.assertIsNone(load_approved(goldens, profile))
            manifest = goldens / profile / "manifest.json"
            write_json(manifest, {
                "schema": 1, "profile": profile,
                "reviewed": True, "reviewer": "", "cases": {},
            })
            with self.assertRaisesRegex(ValueError, "reviewed/complete"):
                load_approved(goldens, profile)
            with self.assertRaises(ValueError):
                approve_candidates(folder, goldens, reviewer="")

    def test_candidate_capture_can_never_auto_promote_itself(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            capture = root / "candidate"
            rows = {}
            for target, mode, dpi, phase in EXPECTED:
                key = case_id(target, mode, dpi, phase)
                path = capture / "actual" / (key + ".png")
                path.parent.mkdir(parents=True, exist_ok=True)
                # Only digest/integrity validation; these bytes are explicitly
                # NOT image captures and MUST NOT be approved.
                path.write_bytes(("not a Qt screenshot " + key).encode("utf-8"))
                rows[key] = {"target": target, "mode": mode, "dpi": dpi,
                             "phase": phase, "width": 640, "height": 480,
                             "capture_status": "captured",
                             "sha256": fingerprint(path)}
            report = {"schema": 1, "profile": profile_id("linux", "6.8.3"),
                      "os": "linux", "qt": "6.8.3",
                      "capture_complete": True, "cases": rows,
                      "parity_pass": False, "release_certified": False}
            write_json(capture / "r52-visual.json", report)
            with self.assertRaisesRegex(ValueError, "parity"):
                approve_candidates(capture, root / "goldens", reviewer="QA")
            self.assertFalse((root / "goldens").exists())

    def test_visual_harness_captures_real_shared_qml(self):
        script = (ROOT / "scripts/r52_visual_goldens.py").read_text("utf-8")
        self.assertIn("view.grabWindow()", script)
        self.assertIn("view.grabFramebuffer()", script)
        self.assertIn("QT_SCALE_FACTOR", script)
        self.assertIn("setLightingProfile", script)
        self.assertIn("reference_projection", script)
        self.assertNotIn("Canvas {", script)


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "PySide6 required for real RGBA pixel-comparison unit tests")
class R52PixelComparatorTests(unittest.TestCase):
    def test_tolerance_and_dimension_difference(self):
        from PySide6.QtGui import QImage, QColor
        from drawtemp.quality.visual import compare_png
        with TemporaryDirectory() as folder:
            a, b = Path(folder) / "a.png", Path(folder) / "b.png"
            first = QImage(16, 16, QImage.Format_RGBA8888)
            first.fill(QColor("#112233"))
            self.assertTrue(first.save(str(a), "PNG"))
            self.assertTrue(first.save(str(b), "PNG"))
            self.assertTrue(compare_png(a, b)["passed"])
            second = QImage(str(b))
            second.setPixelColor(3, 4, QColor("#ffffff"))
            self.assertTrue(second.save(str(b), "PNG"))
            self.assertFalse(compare_png(a, b, max_changed_fraction=0)["passed"])
            self.assertTrue(compare_png(a, b, max_changed_fraction=0.02)["passed"])
            larger = QImage(17, 16, QImage.Format_RGBA8888)
            larger.fill(QColor("#112233"))
            self.assertTrue(larger.save(str(b), "PNG"))
            with self.assertRaisesRegex(ValueError, "dimensions differ"):
                compare_png(a, b)


if __name__ == "__main__":
    unittest.main()
