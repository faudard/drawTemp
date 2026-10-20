"""R52.B1: ambient presets and Studio/Player presentation without CT mutation."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest

from drawtemp.render.ambient_presentation import (
    AmbientTransition, camera_presets, normalize_lighting_profile,
    resolve_camera_preset, sample_lighting,
)


ROOT = Path(__file__).resolve().parents[1]


class AmbientPresetTests(unittest.TestCase):
    def test_default_is_visually_transparent_and_serializable(self):
        profile = normalize_lighting_profile()
        self.assertEqual(profile["phase"], 0)
        self.assertEqual(sample_lighting(profile, 0)["opacity"], 0)
        import json
        self.assertEqual(normalize_lighting_profile(json.loads(json.dumps(profile))),
                         profile)

    def test_strict_validation_rejects_malformed_and_untrusted_effects(self):
        bad = (
            {"version": True}, {"version": 2}, {"unknown": "value"},
            {"nightTint": "red"}, {"dayTint": "#00000000"},
            {"phase": float("nan")}, {"phase": float("inf")},
            {"phase": True}, {"phase": -1}, {"phase": 1.01},
            {"nightOpacity": 10}, {"dayOpacity": None},
            {"shadow": {"path": "/tmp/untrusted.glsl"}},
        )
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ValueError):
                normalize_lighting_profile(item)

    def test_tint_blends_and_transition_is_deterministic(self):
        profile = normalize_lighting_profile({
            "dayTint": "#000000", "nightTint": "#ffffff",
            "dayOpacity": 0, "nightOpacity": 0.8,
        })
        self.assertEqual(sample_lighting(profile, 0)["color"], "#000000")
        self.assertEqual(sample_lighting(profile, 1)["color"], "#ffffff")
        self.assertAlmostEqual(sample_lighting(profile, 0.5)["opacity"], 0.4)
        fast = AmbientTransition(phase=0)
        slow = AmbientTransition(phase=0)
        fast.start(1.0, 1000)
        slow.start(1.0, 1000)
        for delta in (125, 125, 250, 500):
            fast.advance(delta)
        for delta in (500, 500):
            slow.advance(delta)
        self.assertEqual(fast.phase, 1.0)
        self.assertEqual(slow.phase, fast.phase)
        self.assertFalse(fast.active)
        initial = AmbientTransition(phase=1)
        initial.start(0, 1000)
        self.assertAlmostEqual(initial.advance(500), .5)
        self.assertEqual(initial.advance(500), 0)
        for delta in (0, 1001, True):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                initial.advance(delta)

    def test_transition_changes_only_owned_visual_phase(self):
        profile = normalize_lighting_profile()
        transition = AmbientTransition(0)
        transition.start(1.0, 200)
        self.assertTrue(transition.active)
        middle = transition.advance(100)
        self.assertAlmostEqual(middle, 0.5)
        self.assertEqual(profile["phase"], 0.0)
        self.assertEqual(transition.advance(100), 1.0)
        self.assertFalse(transition.active)
        transition.start(0.25, 0)
        self.assertEqual(transition.phase, 0.25)
        for duration in (-1, 60001, 1.5, True):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                transition.start(0, duration)

    def test_camera_modes_are_fail_closed_without_side_picking(self):
        for mode in ("isometric", "top_down"):
            configs = camera_presets(mode)
            self.assertEqual(sum(x["enabled"] for x in configs), 2)
            self.assertFalse(next(x for x in configs if x["id"] == "side-preview")["enabled"])
            with self.assertRaises(ValueError):
                resolve_camera_preset("side-preview", mode)
        self.assertEqual(resolve_camera_preset("iso-wide", "isometric")["zoom"], 0.7)
        self.assertEqual(resolve_camera_preset("top-close", "top_down")["zoom"], 1.5)
        with self.assertRaises(ValueError):
            resolve_camera_preset("not-a-preset", "top_down")

    def test_qml_uses_common_presentation_without_second_canvas(self):
        for name in ("IsoViewport.qml", "TopDownViewport.qml"):
            source = (ROOT / "drawtemp/render" / name).read_text(encoding="utf-8")
            self.assertIn("renderer.lightingOverlay", source)
            self.assertIn("renderer.lightingAnimating", source)
            self.assertIn("renderer.advanceLighting(interval)", source)
            self.assertNotIn("Canvas {", source)
        editor = (ROOT / "drawtemp/studio/map_editor.py").read_text(encoding="utf-8")
        self.assertIn("RenderLookInspector(self.renderer", editor)


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "Optional PySide6 required for Qt smoke")
class AmbientQtTests(unittest.TestCase):
    def test_same_shared_controller_works_in_studio_and_player_projections(self):
        source = """
import sys
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQuickWidgets import QQuickWidget
from drawtemp.render.iso_scene import scene_from_mission
from drawtemp.render.qt_viewport import make_controller
from drawtemp.sdk.reference import MISSION, reference_project
content, _ = reference_project()
scene = scene_from_mission(content.missions[MISSION])
app = QApplication.instance() or QApplication([])
renderer = make_controller(scene, projection_mode=sys.argv[1])
before = renderer.items
original_cell = renderer.cellAt(480, 270)
renderer.setLightingProfile({"nightTint": "#101a44", "phase": 0.25})
renderer.transitionLighting(1, 200)
renderer.advanceLighting(100)
assert abs(renderer.lightingOverlay["phase"] - 0.625) < 1e-9
assert renderer.items == before
renderer.advanceLighting(100)
assert not renderer.lightingAnimating
assert renderer.lightingOverlay["phase"] == 1.0
renderer.setCameraPreset(sys.argv[2])
assert renderer.items != []  # camera culling still functional
assert renderer.cellAt(renderer.camera.width / 2, renderer.camera.height / 2) == original_cell
try:
    renderer.setCameraPreset("side-preview")
except ValueError:
    pass
else:
    raise AssertionError("unsupported side view silently enabled")
from drawtemp.studio.r52_render_inspector import RenderLookInspector
widget = RenderLookInspector(renderer)
baseline = renderer.lightingProfile
widget.night_tint.setText("not-a-color")
assert not widget.preview()
assert renderer.lightingProfile == baseline
widget.night_tint.setText("#25336a")
assert widget.preview()
widget.cancel()
assert renderer.lightingProfile == baseline
view = QQuickWidget()
renderer.attach_engine(view.engine())
view.rootContext().setContextProperty("renderer", renderer)
view.setResizeMode(QQuickWidget.SizeRootObjectToView)
qml = Path("drawtemp/render") / sys.argv[3]
view.setSource(QUrl.fromLocalFile(str(qml.resolve())))
assert view.rootObject() is not None, str(view.errors())
view.resize(960, 640)
view.show()
app.processEvents()
view.close()
widget.close()
"""
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   QT_QUICK_BACKEND="software")
        for mode, preset, qml in (
            ("isometric", "iso-close", "IsoViewport.qml"),
            ("top_down", "top-wide", "TopDownViewport.qml"),
        ):
            with self.subTest(mode=mode):
                run = subprocess.run(
                    [sys.executable, "-c", source, mode, preset, qml],
                    cwd=ROOT, env=env, text=True, capture_output=True, timeout=45)
                self.assertEqual(run.returncode, 0, run.stderr + run.stdout)


if __name__ == "__main__":
    unittest.main()
