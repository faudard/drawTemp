"""R7 Qt smoke: actual shared QML viewport consumes exported actor art."""
import os
from pathlib import Path
import tempfile
import unittest

from drawtemp.assets.characters import export_pack, starter_library
from drawtemp.render.iso_scene import render_items, Camera


ROOT = Path(__file__).resolve().parents[1]


class R7QtIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PIL import Image
            from PySide6.QtGui import QGuiApplication
        except ImportError:
            raise unittest.SkipTest("PySide6 and Pillow required")
        cls.app = QGuiApplication.instance() or QGuiApplication(["drawtemp-r7-test"])

    def test_renderer_displays_actual_animated_sprite_and_fallback(self):
        from drawtemp.render.qt_viewport import make_controller
        with tempfile.TemporaryDirectory() as folder:
            pack_dir = Path(folder)
            export_pack(starter_library()["jeanne"], ROOT, pack_dir)
            # No game state required: this is the exact R3 scene contract.
            scene = {
                "mission": "r7_preview", "width": 4, "height": 4, "revision": 0,
                "tiles": [{"x": x, "y": y, "height": 0, "surface": "grass",
                           "feature": "", "blocked": False, "cover": 0,
                           "hazard": 0, "goal": False}
                          for x in range(4) for y in range(4)],
                "actors": [
                    {"id": "jeanne", "name": "Jeanne", "x": 2, "y": 2, "level": 0,
                     "team": "player", "alive": True, "direction": "west"},
                    {"id": "wolf", "name": "Loup", "x": 1, "y": 2, "level": 0,
                     "team": "enemy", "alive": True, "direction": "north"},
                ],
                "objects": [],
            }
            controller = make_controller(scene, character_pack=pack_dir)
            jeanne = next(row for row in controller.items if row["id"] == "jeanne")
            wolf = next(row for row in controller.items if row["id"] == "wolf")
            self.assertEqual(jeanne["spritePivot"], [32, 63])
            self.assertTrue(jeanne["spriteUrl"].startswith("file:"))
            self.assertEqual(jeanne["spriteRegion"][2:], [64, 64])
            self.assertNotIn("spriteReady", wolf)
            self.assertTrue(controller.play_actor("jeanne", "attack"))
            self.assertFalse(controller.play_actor("wolf", "attack"))
            with self.assertRaises(ValueError):
                controller.set_outfit("jeanne", "armor")
            with self.assertRaises(ValueError):
                controller.play_actor("jeanne", "invalid")
            controller.set_outfit("jeanne", "historical")
            scene["actors"][0]["direction"] = "north"
            controller.refresh()
            north = next(row for row in controller.items if row["id"] == "jeanne")
            self.assertNotEqual(north["spriteRegion"], jeanne["spriteRegion"])
            controller._sprite_timer.stop()

    def test_qml_component_creates_native_scenegraph_with_actor_texture(self):
        from drawtemp.render.qt_viewport import create_view
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            export_pack(starter_library()["jeanne"], ROOT, folder)
            scene = {
                "mission": "r7_smoke", "width": 1, "height": 1, "revision": 0,
                "tiles": [{"x": 0, "y": 0, "height": 0, "surface": "grass",
                           "feature": "", "blocked": False, "cover": 0,
                           "hazard": 0, "goal": False}],
                "actors": [{"id": "jeanne", "name": "Jeanne", "x": 0, "y": 0,
                            "level": 0, "team": "player", "alive": True,
                            "direction": "south"}],
                "objects": [],
            }
            view, controller = create_view(scene, character_pack=folder)
            try:
                view.show()
                self.app.processEvents()
                self.assertIsNotNone(view.rootObject())
                row = next(item for item in controller.items if item["kind"] == "actor")
                self.assertTrue(row["spriteReady"])
            finally:
                controller._sprite_timer.stop()
                view.close()
                view.deleteLater()


if __name__ == "__main__":
    unittest.main()
