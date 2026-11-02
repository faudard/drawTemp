"""Qt offscreen smoke: editor 2D tileset preview and shared Player image provider."""
from __future__ import annotations

import importlib.util
import os
import unittest

QT_AVAILABLE = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(QT_AVAILABLE, "PySide6 Qt 6 is optional")
class QuarterAutotileQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_provider_opaque_quadrant_sprite_and_cache_limit(self):
        from PySide6.QtGui import QColor
        from drawtemp.render.autotile2d import encode_key
        from drawtemp.render.topdown_image_provider import make_topdown_image_provider

        provider = make_topdown_image_provider(max_images=2)
        empty = ["grass"] * 8
        north = empty.copy()
        north[0] = "stone"
        n = encode_key("grass", north)
        plain = encode_key("grass", empty)
        normal = provider.requestImage(plain, None, None)
        transition = provider.requestImage(n, None, None)
        self.assertEqual((normal.width(), normal.height()), (64, 64))
        self.assertFalse(normal.isNull())
        self.assertNotEqual(normal.pixelColor(32, 0),
                            transition.pixelColor(32, 0))
        self.assertEqual(normal.pixelColor(32, 48),
                         transition.pixelColor(32, 48))
        provider.requestImage(encode_key("water", empty), None, None)
        self.assertEqual(len(provider.entries), 2)
        self.assertTrue(provider.requestImage("../../", None, None).isNull())

    def test_studio_projection_preserves_renderer_camera_and_document(self):
        from PySide6.QtQuickWidgets import QQuickWidget
        from drawtemp.studio.map_editor import MapWindow
        from drawtemp.studio.map_authoring import MapStudio

        studio = MapStudio.reference()
        window = MapWindow(studio)
        try:
            viewport = window.viewport
            controller = window.renderer
            original_zoom = controller.camera.zoom
            before = studio.snapshot()
            window.projection_choice.setCurrentIndex(1)
            self.assertIs(window.viewport, viewport)
            self.assertIs(window.renderer, controller)
            self.assertEqual(controller.projection_mode, "top_down")
            self.assertEqual(window.viewport.status(), QQuickWidget.Ready)
            self.assertEqual(window.viewport.rootObject().property("interactionMode"), "edit")
            self.assertTrue(window.tileset_panel.items.count() >= 8)
            self.assertEqual(studio.snapshot(), before)
            self.assertEqual(controller.camera.zoom, original_zoom)
            topdown_tiles = [r for r in controller.items if r["kind"] == "tile"]
            self.assertTrue(topdown_tiles)
            self.assertTrue(all(r.get("autotileKey") for r in topdown_tiles))
            window.tileset_panel.set_material("stone")
            window.tileset_panel.items.setCurrentRow(3)
            self.assertEqual(window.material.currentText(), "stone")

            window.projection_choice.setCurrentIndex(0)
            self.assertEqual(controller.projection_mode, "isometric")
            self.assertEqual(window.viewport.status(), QQuickWidget.Ready)
            self.assertEqual(controller.camera.zoom, original_zoom)
            self.assertEqual(studio.snapshot(), before)
        finally:
            window.close()
            window.deleteLater()

    def test_camera_projection_recenter_does_not_change_zoom(self):
        from drawtemp.render.qt_viewport import make_controller
        from drawtemp.sdk.reference import reference_project
        from drawtemp.render.iso_scene import scene_from_mission

        content, _ = reference_project()
        scene = scene_from_mission(next(iter(content.missions.values())))
        controller = make_controller(scene, projection_mode="top_down")
        zoom = controller.camera.zoom
        pan = controller.camera.pan_x
        controller.setProjectionMode("isometric")
        self.assertEqual(controller.camera.zoom, zoom)
        controller.setProjectionMode("top_down")
        self.assertEqual(controller.camera.zoom, zoom)
        self.assertAlmostEqual(controller.camera.pan_x, pan, places=4)


if __name__ == "__main__":
    unittest.main()
