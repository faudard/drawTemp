"""INT-01: R3 is the sole scenegraph and projection for R5/R12.

Headless gates test parity/selection semantics; Qt gates instantiate the real
QQuickWidget and QML root. Offscreen runs do NOT certify a hardware GPU.
"""
import importlib.util
from pathlib import Path
import os
import subprocess
import sys
import unittest

from drawtemp.core import Content
from drawtemp.player.controller import PlayerController
from drawtemp.player.qt_app import scene_for_player
from drawtemp.render.iso_scene import (
    Camera, IsoProjection, fingerprint, render_items,
    scene_from_exploration, scene_from_mission,
)
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.map_authoring import MapStudio

ROOT = Path(__file__).resolve().parents[1]


class SharedRendererContractTests(unittest.TestCase):
    def test_map_edits_are_the_same_scene_and_metadata_as_player(self):
        studio = MapStudio.reference()
        studio.paint([(4, 3)], "surface:stone")
        studio.paint([(5, 2)], "height+")
        snapshot = studio.snapshot()
        content = Content.from_dict(snapshot["content"])
        original = content.missions[MISSION]
        authored = scene_from_mission(original)
        player_scene = scene_from_mission(content.missions[MISSION])
        self.assertEqual(fingerprint(authored), fingerprint(player_scene))
        tile = next(tile for tile in authored["tiles"]
                    if (tile["x"], tile["y"]) == (4, 3))
        self.assertEqual(tile["surface"], "stone")
        self.assertEqual(len(authored["tiles"]),
                         original.board.width * original.board.height)
        items = render_items(authored, Camera())
        self.assertTrue(any(row["kind"] == "tile" and row["surface"] == "stone"
                            for row in items))
        self.assertEqual(original.board.tile((5, 2)).height,
                         next(row["height"] for row in authored["tiles"]
                              if (row["x"], row["y"]) == (5, 2)))

    def test_player_battle_uses_exact_r3_snapshot(self):
        content, project = reference_project()
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            controller = PlayerController(content, project, "main", folder)
            controller.new_game()
            controller.choose("enter")
            controller.start_mission(MISSION)
            before = controller.session.snapshot()
            scene = scene_for_player(controller)
            self.assertEqual(scene, scene_from_mission(content.missions[MISSION], before))
            self.assertEqual(scene["revision"], before.revision)
            self.assertEqual(len(scene["actors"]), len(before.battle["units"]))
            controller.select_cell(3, 4)
            self.assertEqual(scene_for_player(controller), scene)
            controller.save(1)
            controller.load(1)
            self.assertEqual({**scene_for_player(controller), "revision": 0},
                             {**scene, "revision": 0})

    def test_exploration_uses_one_scene_and_keeps_rules_headless(self):
        from drawtemp.player.qt_app import build_controller
        controller = build_controller(reference=False)
        controller.new_game()
        state = controller.session.snapshot()
        self.assertIsNotNone(state.exploration)
        scene = scene_for_player(controller)
        self.assertEqual(scene, scene_from_exploration(state.exploration,
                                                      revision=state.revision))
        self.assertEqual(scene["width"], state.exploration["width"])
        self.assertEqual(scene["height"], state.exploration["height"])
        self.assertTrue(any(a["id"] == "jeanne" for a in scene["actors"]))
        self.assertEqual(len(scene["objects"]),
                         len(state.exploration["interactions"]))
        before = fingerprint(scene)
        controller.explore_move(1, 0)
        self.assertNotEqual(before, fingerprint(scene_for_player(controller)))

    def test_projection_and_height_picking_reused_by_both_clients(self):
        projection = IsoProjection()
        content, _ = reference_project()
        scene = scene_from_mission(content.missions[MISSION])
        camera = Camera(width=850, height=580)
        center = projection.project(4, 4)
        camera.center(*center)
        for zoom in (0.6, 1.0, 1.7, 2.5):
            camera.zoom = zoom
            camera.center(*center)
            for cell in ((0, 1), (3, 4), (5, 2)):
                x, y = cell
                tile = next(t for t in scene["tiles"] if (t["x"], t["y"]) == cell)
                sx, sy = camera.screen(*projection.project(x, y, tile["height"]))
                wx, wy = camera.world(sx, sy)
                heights = {(t["x"], t["y"]): t["height"]
                           for t in scene["tiles"] if t["height"]}
                self.assertEqual(projection.pick(wx, wy, scene["width"],
                                                 scene["height"], heights), cell)

    def test_no_parallel_qml_canvas_or_hidden_second_scene(self):
        renderer = (ROOT / "drawtemp/render/IsoViewport.qml").read_text("utf-8")
        board = (ROOT / "drawtemp/render/TacticalBoard.qml").read_text("utf-8")
        editor = (ROOT / "drawtemp/studio/map_editor.py").read_text("utf-8")
        self.assertIn("Repeater {", renderer)
        self.assertIn("ShapePath {", renderer)
        self.assertNotIn("Canvas {", renderer)
        self.assertIn("IsoViewport {", board)
        self.assertNotIn("Canvas {", board)
        self.assertIn("IsoViewport.qml", editor)
        self.assertNotIn("MapDraft.qml", editor)


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "PySide6 optional in headless CI")
class SharedRendererQtSmoke(unittest.TestCase):
    def test_editor_uses_live_r3_controller_and_can_edit(self):
        from PySide6.QtWidgets import QApplication
        from drawtemp.studio.map_editor import MapWindow
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        app = QApplication.instance() or QApplication([])
        window = MapWindow()
        try:
            root = window.viewport.rootObject()
            self.assertIsNotNone(root)
            self.assertEqual(root.property("interactionMode"), "edit")
            self.assertEqual(window.renderer.scene["mission"], MISSION)
            projection = window.renderer.projection
            camera = window.renderer.camera
            pos = (2, 2)
            sx, sy = camera.screen(*projection.project(*pos))
            self.assertEqual(window.renderer.cellAt(sx, sy),
                             {"x": pos[0], "y": pos[1]})
            window.material.setCurrentText("stone")
            window.begin_stroke(*pos)
            window.finish_stroke(*pos)
            self.assertEqual(window.studio.sample(pos), "stone")
            self.assertIsNotNone(window.viewport.rootObject())
            self.assertEqual(window.renderer.scene["mission"], MISSION)
        finally:
            # Qt's dirty-document close dialog would be modal in an offscreen test.
            # This is a viewport smoke, not an interactive discard confirmation.
            window.hide()
            window.deleteLater()

    def test_player_instantiates_the_same_qml_with_reference_scene(self):
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   QT_QUICK_BACKEND="software")
        completed = subprocess.run(
            [sys.executable, "-m", "drawtemp.player.qt_app", "--reference", "--smoke"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
