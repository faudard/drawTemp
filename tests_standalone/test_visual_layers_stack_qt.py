"""Qt6 visual layer alpha masks and map editor/Player projection smoke."""
from __future__ import annotations

import importlib.util
import os
import unittest

QT_AVAILABLE = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(QT_AVAILABLE, "Optional PySide6 is not installed")
class VisualLayerQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_mask_rgba_quadrants_and_provider_bounded_cache(self):
        from drawtemp.render.topdown_image_provider import make_topdown_image_provider
        from sporebound.visual_layers import visual_image_key

        provider = make_topdown_image_provider(max_images=2)
        mask = [255, 0, 127, 255]
        image = provider.requestImage(visual_image_key("grass", mask), None, None)
        self.assertEqual((image.width(), image.height()), (64, 64))
        self.assertEqual(image.pixelColor(10, 10).alpha(), 255)
        self.assertEqual(image.pixelColor(52, 10).alpha(), 0)
        self.assertEqual(image.pixelColor(10, 52).alpha(), 127)
        self.assertEqual(image.pixelColor(52, 52).alpha(), 255)
        self.assertTrue(provider.requestImage("../invalid", None, None).isNull())
        for value in (0, 32, 255):
            provider.requestImage(visual_image_key("dirt", [value] * 4), None, None)
        self.assertLessEqual(len(provider.entries), 2)

    def test_studio_2d_layer_paint_is_canonical_and_preserves_base_terrain(self):
        from drawtemp.studio.map_authoring import MapStudio
        from drawtemp.studio.map_editor import MapWindow

        studio = MapStudio.reference()
        window = MapWindow(studio)
        try:
            before = studio.snapshot()["content"]
            window.projection_choice.setCurrentIndex(1)
            self.assertEqual(window.renderer.projection_mode, "top_down")
            self.assertTrue(window.visual_layers_dock.isVisible() or
                            not window.isVisible())
            window.visual_layers_editor.create("smoke", "Smoke")
            window.visual_layers_panel.refresh()
            item = next(
                window.visual_layers_panel.tree.topLevelItem(i)
                for i in range(window.visual_layers_panel.tree.topLevelItemCount())
                if window.visual_layers_panel.tree.topLevelItem(i).data(0, 256) == "smoke")
            window.visual_layers_panel.tree.setCurrentItem(item)
            window.visual_layers_panel.mode.setCurrentText("Layer Paint")
            window.material.setCurrentText("sand")
            window.begin_stroke(1, 1)
            window.finish_stroke(1, 1)
            self.assertEqual(studio.snapshot()["content"], before)
            rows = [row for row in window.renderer.items
                    if row["kind"] == "visual-layer"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["material"], "sand")
            window.visual_layers_panel.mode.setCurrentText("Mask Paint")
            for input_, val in zip(window.visual_layers_panel.quarters.values(),
                                   (0, 255, 128, 0)):
                input_.setValue(val)
            window.begin_stroke(1, 1)
            window.finish_stroke(1, 1)
            self.assertEqual(window.visual_layers_editor.layers()[0][
                "cells"][0]["mask"], [0, 255, 128, 0])
            self.assertEqual(studio.snapshot()["content"], before)
        finally:
            # Cleanly leave the GUI without unsaved-content confirmation.
            while studio.authoring.snapshot().can_undo:
                studio.undo()
            window.close()
            window.deleteLater()

    def test_player_and_editor_share_scene_compositor_without_isometric_changes(self):
        from drawtemp.sdk.reference import reference_project
        from drawtemp.render.iso_scene import scene_from_mission, TopDownProjection, Camera, render_items
        from sporebound.visual_layers import attach_visual_layers

        content, project = reference_project()
        mission = next(iter(content.missions.values()))
        scene = attach_visual_layers(scene_from_mission(mission),
                                     project.extensions)
        self.assertEqual(scene["visual_layers"], [])
        self.assertFalse(any(r["kind"] == "visual-layer" for r in
                             render_items(scene, Camera(900, 700), TopDownProjection()))


if __name__ == "__main__":
    unittest.main()
