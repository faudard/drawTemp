"""R52.B2 — side-on camera, picking, R3 parity and fail-closed Qt smoke."""
from copy import deepcopy
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest

from drawtemp.render import (Camera, SideProjection, IsoProjection,
                             TopDownProjection, pick, render_items)
from drawtemp.render.depth_pipeline import (
    normalize_depth_profile, world_to_screen, screen_to_world)
from drawtemp.render.ambient_presentation import (
    camera_presets, resolve_camera_preset)


ROOT = Path(__file__).resolve().parents[1]


def fixture(*, size=8):
    return {
        "mission": "r52b2-side", "width": size, "height": size,
        "tiles": [
            {"x": x, "y": y, "surface": "stone", "height":
                2 if (x, y) == (4, 3) else 0,
             "feature": "", "blocked": False, "cover": 0,
             "hazard": 0, "goal": False}
            for y in range(size) for x in range(size)],
        "actors": [{"id": "hero", "name": "Hero", "x": 2.0, "y": 2.0,
                    "level": 0, "team": "player", "alive": True}],
        "objects": [{"id": "chest", "kind": "chest", "x": 6, "y": 4}],
        "structures": [], "interior_floors": [],
    }


class SideProjectionTests(unittest.TestCase):
    def test_roundtrip_world_and_elevation_plane(self):
        p = SideProjection()
        self.assertEqual((p.width, p.height, p.height_step), (64, 24, 12))
        for x in (0, 2.25, 5):
            for y in (0, 3.5, 7):
                for z in (-2, 0, 1, 3):
                    with self.subTest(x=x, y=y, z=z):
                        sx, sy = p.project(x, y, z)
                        nx, ny = p.unproject(sx, sy, z)
                        self.assertAlmostEqual(nx, x)
                        self.assertAlmostEqual(ny, y)

    def test_picking_raised_tile_beats_occluded_ground_lane(self):
        p = SideProjection()
        scene = fixture()
        elevations = {(row["x"], row["y"]): row["height"]
                      for row in scene["tiles"] if row["height"]}
        raised = p.project(4, 3, 2)
        self.assertEqual(raised, p.project(4, 2))
        self.assertEqual(p.pick(*raised, 8, 8, elevations), (4, 3))
        self.assertEqual(p.pick(*p.project(1, 1), 8, 8, elevations), (1, 1))
        self.assertIsNone(p.pick(-1000, -1000, 8, 8, elevations))

    def test_visual_front_platform_occludes_back_actor_for_picking(self):
        scene = fixture()
        scene["actors"][0]["x"] = 4.0
        scene["actors"][0]["y"] = 2.0
        p = SideProjection()
        camera = Camera(width=960, height=540)
        sx, sy = world_to_screen(camera, p, 4, 3, elevation=2)
        self.assertEqual(
            pick(scene, camera, sx, sy, p),
            {"kind": "tile", "cell": [4, 3]},
        )
        rows = render_items(scene, camera, p)
        surface = next(row for row in rows if row["id"] == "tile:4:3")
        actor = next(row for row in rows if row["id"] == "hero")
        self.assertGreater(surface["zOrder"], actor["zOrder"])

    def test_screen_space_picking_pan_zoom_and_depth_are_consistent(self):
        p = SideProjection()
        scene = fixture()
        reference = deepcopy(scene)
        for width, height, zoom, px, py in (
            (960, 540, 1.0, 0, 0),
            (640, 480, 2.1, 135, -61),
            (1280, 720, 0.65, -84, 92),
        ):
            camera = Camera(width, height, zoom, px, py)
            for x, y, z in ((1, 1, 0), (4, 3, 2), (5, 5, 0)):
                sx, sy = world_to_screen(camera, p, x, y, elevation=z)
                wx, wy = screen_to_world(camera, p, sx, sy, elevation=z)
                self.assertAlmostEqual(wx, x)
                self.assertAlmostEqual(wy, y)
                self.assertEqual(
                    pick(scene, camera, sx, sy, p),
                    {"kind": "tile", "cell": [x, y]})
            sx, sy = world_to_screen(camera, p, 2, 2)
            self.assertEqual(pick(scene, camera, sx, sy, p),
                             {"kind": "actor", "id": "hero"})
            sx, sy = world_to_screen(camera, p, 6, 4)
            self.assertEqual(pick(scene, camera, sx, sy, p),
                             {"kind": "object", "id": "chest"})
            rows = render_items(scene, camera, p)
            self.assertEqual(rows, sorted(rows, key=lambda row:
                                           (row["zOrder"], row["id"])))
            self.assertEqual(len({row["id"] for row in rows}), len(rows))
        self.assertEqual(scene, reference)

    def test_culling_keeps_bounded_tiles_on_large_side_world(self):
        scene = fixture(size=128)
        p = SideProjection()
        camera = Camera(width=400, height=260)
        camera.center(*p.project(60, 60))
        rows = render_items(scene, camera, p)
        tile_count = len([row for row in rows if row["kind"] == "tile"])
        self.assertGreater(tile_count, 0)
        self.assertLess(tile_count, 128 * 128 // 4)

    def test_structures_fail_closed_at_headless_layer(self):
        scene = fixture()
        scene["structures"] = [{"id": "house"}]
        camera = Camera()
        for fn in (lambda: render_items(scene, camera, SideProjection()),
                   lambda: pick(scene, camera, 100, 100, SideProjection())):
            with self.assertRaisesRegex(ValueError, "R6 buildings"):
                fn()
        # Existing projection contracts remain intact for authored buildings.
        normalize_depth_profile({"projection": "isometric"},
                                projection_mode="isometric")

    def test_side_preset_and_depth_profile_gate(self):
        presets = camera_presets("side")
        self.assertEqual(sum(item["enabled"] for item in presets), 2)
        self.assertEqual(resolve_camera_preset("side-preview", "side")["zoom"], 1)
        self.assertEqual(resolve_camera_preset("side-close", "side")["zoom"], 1.5)
        with self.assertRaises(ValueError):
            resolve_camera_preset("iso-wide", "side")
        profile = normalize_depth_profile(
            {"projection": "side", "layers": [{
                "id": "backdrop", "x": 1, "y": 1, "width": 200,
                "height": 80, "parallax": 0.3, "color": "#4488aa",
                "opacity": 0.75}]}, projection_mode="side")
        self.assertEqual(profile["projection"], "side")
        with self.assertRaises(ValueError):
            normalize_depth_profile(profile, projection_mode="top_down")

    def test_qml_and_studio_reference_single_shared_view(self):
        qml = (ROOT / "drawtemp/render/TopDownViewport.qml").read_text("utf-8")
        self.assertIn("renderer.projectionMode === \"side\"", qml)
        self.assertIn("viewport.flatView", qml)
        self.assertIn("row.height", qml)
        self.assertIn("renderer.pickAt", qml)
        self.assertNotIn("Canvas {", qml)
        source = (ROOT / "drawtemp/studio/map_editor.py").read_text("utf-8")
        self.assertIn('create_view(scene, projection_mode="side")', source)


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "Qt optional in pure headless testing")
class SideQtSmoke(unittest.TestCase):
    def test_qquickview_and_controller_share_side_projection(self):
        source = r"""
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from drawtemp.render.qt_viewport import create_view
from drawtemp.render.iso_scene import SideProjection
from drawtemp.render.depth_pipeline import world_to_screen
app = QGuiApplication.instance() or QGuiApplication([])
scene = {"mission": "side-smoke", "width": 8, "height": 8,
         "tiles": [{"x": x, "y": y, "height": 0, "surface": "stone"}
                   for y in range(8) for x in range(8)],
         "actors": [], "objects": [], "structures": [], "interior_floors": []}
view, renderer = create_view(scene, projection_mode="side")
assert isinstance(renderer.projection, SideProjection)
assert view.rootObject() is not None, str(view.errors())
assert renderer.projectionMode == "side"
assert not renderer.textureBatching
renderer.resizeViewport(960, 540)
renderer.setCameraPreset("side-close")
renderer.setDepthProfile({"projection": "side", "layers": []})
renderer.setLightingProfile({"phase": 0.5})
assert renderer.lightingOverlay["phase"] == 0.5
sx, sy = world_to_screen(renderer.camera, renderer.projection, 2, 2)
assert renderer.cellAt(sx, sy) == {"x": 2, "y": 2}
original = renderer.scene
try:
    renderer.replace_scene({**scene, "structures": [{"id": "house"}]})
except ValueError:
    pass
else:
    raise AssertionError("R6 side scene unexpectedly accepted")
assert renderer.scene is original
view.resize(960, 540)
view.show()
app.processEvents()
assert view.rootObject() is not None
view.close()
"""
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   QT_QUICK_BACKEND="software")
        out = subprocess.run([sys.executable, "-c", source], cwd=ROOT,
                             env=env, capture_output=True, text=True, timeout=45)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
