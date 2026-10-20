"""R52.A regression fixtures: view transforms, depth layers and fail-closed effects."""
import importlib.util
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest

from drawtemp.render.iso_scene import (Camera, IsoProjection, TopDownProjection,
                                       pick, render_items)
from drawtemp.render.depth_pipeline import (
    MAX_LAYERS, backend_plan, decoration_screen_point, effect_capabilities,
    normalize_depth_profile, projected_depth_layers, screen_to_world,
    world_to_screen,
)


def sample_layer(identifier="far", **updates):
    layer = {"id": identifier, "x": 3.0, "y": 2.0,
             "width": 256, "height": 128, "parallax": 0.35,
             "color": "#446688", "opacity": 0.8}
    layer.update(updates)
    return layer


def sample_scene():
    return {"mission": "r52-depth-fixture", "width": 10, "height": 10,
            "tiles": [{"x": x, "y": y, "height": 0, "surface": "grass"}
                      for y in range(10) for x in range(10)],
            "actors": [], "objects": [], "structures": [], "interior_floors": []}


class DepthPipelineTests(unittest.TestCase):
    def test_disabled_by_default_and_defensive_copy(self):
        empty = normalize_depth_profile()
        self.assertEqual(empty["layers"], [])
        self.assertEqual(empty["effects"], {"lightmap": False, "shadows": False})
        source = {"layers": [sample_layer()]}
        copied = normalize_depth_profile(source)
        source["layers"][0]["x"] = 99
        self.assertEqual(copied["layers"][0]["x"], 3.0)
        self.assertEqual(projected_depth_layers(empty, IsoProjection()), [])

    def test_invalid_profiles_fail_closed_before_mutation(self):
        good = sample_layer()
        bad = [
            {"version": 2}, {"version": True},
            {"projection": "side"}, {"mystery": True},
            {"layers": "not a sequence"},
            {"layers": [good, good]},
            {"layers": [sample_layer() for _ in range(MAX_LAYERS + 1)]},
            {"layers": [sample_layer(color="red")]},
            {"layers": [sample_layer(parallax=1.01)]},
            {"layers": [sample_layer(parallax=float("nan"))]},
            {"layers": [sample_layer(width=float("inf"))]},
            {"layers": [sample_layer(width=999999)]},
            {"layers": [sample_layer(opacity=-0.1)]},
            {"layers": [sample_layer(id="../path")]},
            {"layers": [{**good, "shader": "untrusted"}]},
            {"effects": {"lightmap": "true"}},
            {"effects": {"shaderSource": "user-data"}},
        ]
        for profile in bad:
            with self.subTest(profile=str(profile)[:120]):
                with self.assertRaises(ValueError):
                    normalize_depth_profile(profile)

    def test_decorations_sorted_and_projected_by_shared_r3_geometry(self):
        profile = normalize_depth_profile({"layers": [
            sample_layer("far"), sample_layer("near", x=7, parallax=0.85)]})
        rows = projected_depth_layers(profile, IsoProjection())
        self.assertEqual([row["id"] for row in rows], ["far", "near"])
        self.assertEqual([row["depthIndex"] for row in rows], [0, 1])
        self.assertEqual((rows[0]["sx"], rows[0]["sy"]),
                         IsoProjection().project(3, 2))
        self.assertEqual(rows[0]["color"], "#446688")

    def test_three_camera_fixtures_preserve_roundtrip_picking_and_depth(self):
        scene = sample_scene()
        setups = [
            (IsoProjection(), Camera(width=960, height=540, zoom=1.0)),
            (IsoProjection(), Camera(width=640, height=480, zoom=2.1,
                                     pan_x=135, pan_y=-61)),
            (TopDownProjection(), Camera(width=1200, height=800, zoom=0.65,
                                         pan_x=-83, pan_y=57)),
        ]
        for projection, camera in setups:
            with self.subTest(camera=str(camera), projection=str(projection)):
                rows_before = render_items(scene, camera, projection)
                for x, y in ((1, 1), (3, 4), (7, 2)):
                    sx, sy = world_to_screen(camera, projection, x, y)
                    wx, wy = screen_to_world(camera, projection, sx, sy)
                    self.assertAlmostEqual((wx, wy)[0], x)
                    self.assertAlmostEqual((wx, wy)[1], y)
                    self.assertEqual(pick(scene, camera, sx, sy, projection),
                                     {"kind": "tile", "cell": [x, y]})
                    for factor in (0, 0.35, 1):
                        px, py = decoration_screen_point(camera, projection, x, y,
                                                         parallax=factor)
                        self.assertTrue(math.isfinite(px) and math.isfinite(py))
                        self.assertEqual(pick(scene, camera, sx, sy, projection),
                                         {"kind": "tile", "cell": [x, y]})
                    self.assertEqual(decoration_screen_point(
                        camera, projection, x, y, parallax=1), (sx, sy))
                self.assertEqual(rows_before, render_items(scene, camera, projection))

    def test_feature_fallback_and_advisory_backends(self):
        profile = normalize_depth_profile({"effects": {
            "lightmap": True, "shadows": True}})
        self.assertEqual(effect_capabilities(profile), {
            "lightmapEnabled": False, "shadowsEnabled": False,
            "lightmapFallback": "not-implemented-r52b",
            "shadowsFallback": "not-implemented-r52b",
        })
        self.assertEqual(backend_plan("hardware", hardware_available=False,
                                      software_available=True),
                         {"backend": "software", "fallback": "hardware-unavailable"})
        self.assertEqual(backend_plan("auto", hardware_available=True,
                                      software_available=True)["backend"], "hardware")
        with self.assertRaises(RuntimeError):
            backend_plan("auto", hardware_available=False,
                         software_available=False)
        with self.assertRaises(ValueError):
            backend_plan("invalid", hardware_available=True,
                         software_available=True)



class DepthQmlContractTests(unittest.TestCase):
    def test_both_views_keep_parallax_below_interactive_items(self):
        root = Path(__file__).resolve().parents[1] / "drawtemp" / "render"
        for name in ("IsoViewport.qml", "TopDownViewport.qml"):
            qml = (root / name).read_text(encoding="utf-8")
            self.assertIn("renderer.depthLayers", qml)
            self.assertIn("z: -200000 + layer.depthIndex", qml)
            self.assertIn("parallax", qml)
            self.assertIn("renderer", qml)
        iso = (root / "IsoViewport.qml").read_text(encoding="utf-8")
        self.assertIn("renderer.cellAt", iso)
        self.assertIn("renderer.pickAt", iso)

    @unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                         "PySide6 is optional in headless suites")
    def test_qt_profiles_are_transactional_and_both_qml_views_load(self):
        # Run each QML viewport in an isolated process: no Qt global state
        # leaks into unrelated offscreen or GUI test cases.
        source = """
import sys
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from drawtemp.render.qt_viewport import make_controller
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.render.iso_scene import scene_from_mission
app = QGuiApplication.instance() or QGuiApplication([])
content, _ = reference_project()
scene = scene_from_mission(content.missions[MISSION])
renderer = make_controller(scene, projection_mode=sys.argv[1])
before = renderer.items
profile = {"layers": [{"id": "far", "x": 1, "y": 2,
                        "width": 250, "height": 120,
                        "parallax": 0.4, "color": "#123456",
                        "opacity": 0.8}]}
renderer.setDepthProfile(profile)
assert len(renderer.depthLayers) == 1
assert renderer.items == before
try:
    renderer.setDepthProfile({"layers": [{"id": "../bad"}]})
except ValueError:
    pass
else:
    raise AssertionError("invalid profile accepted")
assert len(renderer.depthLayers) == 1
view = QQuickView()
renderer.attach_engine(view.engine())
view.rootContext().setContextProperty("renderer", renderer)
view.setResizeMode(QQuickView.SizeRootObjectToView)
qml = Path("drawtemp/render") / sys.argv[2]
view.setSource(QUrl.fromLocalFile(str(qml.resolve())))
assert view.rootObject() is not None, str(view.errors())
view.resize(800, 600)
view.show()
app.processEvents()
assert view.rootObject() is not None, str(view.errors())
view.close()
"""
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   QT_QUICK_BACKEND="software")
        root = Path(__file__).resolve().parents[1]
        for mode, qml in (("isometric", "IsoViewport.qml"),
                          ("top_down", "TopDownViewport.qml")):
            with self.subTest(mode=mode):
                result = subprocess.run([sys.executable, "-c", source, mode, qml],
                                        cwd=root, env=env, capture_output=True,
                                        text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
