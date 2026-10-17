"""R17.5: Studio/Player R3 parity (logical rows + real Qt Quick pixels).

Comparison is strict for visual data and picking. Software framebuffer
captures are regression evidence, NOT accepted R14 goldens or GPU timings.
"""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r17_renderer_parity import (
    assert_controller_parity, compare_controller_pair, scene_visual_payload,
)
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.render.iso_scene import scene_from_mission
from drawtemp.player.controller import PlayerController
from drawtemp.player.qt_app import scene_for_player


class RendererParityContracts(unittest.TestCase):
    def test_canonical_scenes_ignore_only_non_visual_revision(self):
        content, project = reference_project()
        studio = scene_from_mission(content.missions[MISSION])
        with TemporaryDirectory() as root:
            player = PlayerController(content, project, "main", root)
            player_scene = scene_for_player(player)
            self.assertEqual(scene_visual_payload(studio),
                             scene_visual_payload(player_scene))
            visual = deepcopy(studio)
            visual["revision"] = 99999
            self.assertEqual(scene_visual_payload(studio),
                             scene_visual_payload(visual))
            visual["tiles"][0]["height"] += 1
            self.assertNotEqual(scene_visual_payload(studio),
                                scene_visual_payload(visual))
            visual = deepcopy(studio)
            visual["actors"][0]["direction"] = (
                "west" if visual["actors"][0]["direction"] != "west" else "east")
            self.assertNotEqual(scene_visual_payload(studio),
                                scene_visual_payload(visual))

    def test_fail_closed_rejects_unknown_scene_schema(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            scene_visual_payload({"mission": MISSION})
        with self.assertRaisesRegex(ValueError, "dictionary"):
            scene_visual_payload(None)


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "R17.5 Qt parity requires optional PySide6")
class RendererParityQt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["r17-renderer-parity"])

    def test_semantic_depth_camera_atlas_layers_and_altitude_picking(self):
        from drawtemp.render.qt_viewport import make_controller
        from drawtemp.studio.map_authoring import MapStudio
        from drawtemp.core import Content

        studio = MapStudio.reference()
        studio.select_map(MISSION)
        studio.paint([(4, 3)], "surface:stone")
        studio.paint([(5, 2)], "height+")
        studio.paint([(4, 4)], "cover")
        document = studio.snapshot()
        content = Content.from_dict(document["content"])
        mission = content.missions[MISSION]
        a = make_controller(scene_from_mission(mission))
        b = make_controller(scene_from_mission(mission))
        for zoom in (0.6, 1.0, 1.75, 2.4):
            for renderer in (a, b):
                renderer.resizeViewport(850, 580)
                renderer.camera.zoom = zoom
                renderer.center_scene()
                renderer.setConstructionView(0, False)
            report = assert_controller_parity(
                a, b, sample_cells=((0, 1), (3, 4), (5, 2), (4, 3)))
            self.assertGreater(report["draw_counts"]["studio"], 0)
            self.assertEqual(report["studio"], report["player"])
            for row in report["sample_picks"]:
                self.assertEqual(row["studio"], row["player"])
        # Verify the gate detects *actual* field and delegate divergence.
        other = deepcopy(b.scene)
        tile = next(x for x in other["tiles"] if (x["x"], x["y"]) == (5, 2))
        tile["height"] += 1
        b.replace_scene(other)
        mismatch = compare_controller_pair(a, b, sample_cells=((5, 2),))
        self.assertFalse(mismatch["passed"])
        self.assertIn("scene", mismatch["differences"])
        self.assertIn("draw_order", mismatch["differences"])

    def test_real_studio_widget_and_player_board_visual_parity(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQuickWidgets import QQuickWidget
        from PySide6.QtTest import QTest
        from drawtemp.studio.map_authoring import MapStudio
        from drawtemp.studio.map_editor import MapWindow
        from drawtemp.render.qt_viewport import make_controller
        from drawtemp.quality.visual import compare_png
        from drawtemp.player.qt_app import build_controller

        with TemporaryDirectory() as folder:
            editor = MapWindow(MapStudio.reference())
            player = build_controller(save_dir=Path(folder) / "saves",
                                      reference=True)
            renderer = make_controller(scene_for_player(player))
            player_view = QQuickWidget()
            renderer.attach_engine(player_view.engine())
            player_view.setResizeMode(QQuickWidget.SizeRootObjectToView)
            player_view.rootContext().setContextProperty("renderer", renderer)
            qml = Path(__file__).resolve().parents[1] / (
                "drawtemp/render/TacticalBoard.qml")
            player_view.setSource(QUrl.fromLocalFile(str(qml)))
            self.assertEqual(player_view.status(), QQuickWidget.Ready,
                             [e.toString() for e in player_view.errors()])
            self.assertIsNotNone(editor.viewport.rootObject())
            board = player_view.rootObject()
            self.assertIsNotNone(board)
            self.assertEqual(board.property("interactionMode"), "select")
            self.assertEqual(editor.viewport.rootObject().property(
                "interactionMode"), "edit")
            # Disable deliberate Player-only tactical overlays for base-scene
            # parity. The two clients must still use their production QML.
            board.setProperty("showTacticalOverlay", False)
            board.setProperty("showLegend", False)
            board.setProperty("showGrid", True)
            editor.viewport.setFixedSize(720, 480)
            player_view.setFixedSize(720, 480)
            try:
                editor.show()
                player_view.show()
                QTest.qWait(250)
                for controller in (editor.renderer, renderer):
                    controller.resizeViewport(720, 480)
                    controller.camera.zoom = 1
                    controller.center_scene()
                report = assert_controller_parity(
                    editor.renderer, renderer,
                    sample_cells=((2, 4), (3, 4), (4, 3)))
                self.assertEqual(report["studio"], report["player"])
                self.assertEqual(editor.viewport.rootObject().property(
                    "showGrid"), board.property("showGrid"))
                capture = Path(os.environ.get("DRAWTEMP_R17_PARITY_DIR",
                           str(Path(folder) / "captures")))
                capture.mkdir(parents=True, exist_ok=True)
                left, right = capture / "studio.png", capture / "player.png"
                self.assertTrue(editor.viewport.grabFramebuffer().save(str(left)))
                self.assertTrue(player_view.grabFramebuffer().save(str(right)))
                pixels = compare_png(
                    left, right, max_channel_delta=12,
                    max_changed_fraction=0.01,
                    diff_path=capture / "studio-player-diff.png")
                (capture / "parity.json").write_text(
                    json.dumps({"contract": report, "pixels": pixels,
                                "backend": "Qt software / offscreen",
                                "gpu_certified": False}, indent=2),
                    encoding="utf-8")
                self.assertTrue(pixels["passed"], pixels)
            finally:
                editor.hide()
                editor.deleteLater()
                player_view.hide()
                player_view.deleteLater()


if __name__ == "__main__":
    unittest.main()
