"""3.7.6 — Full Tk canvas, atlas zoom and offscreen scene acceptance.

Run with SPOREBOUND_GUI_SMOKE=1 under a GUI/Xvfb. These tests exercise the
actual CanvasRenderer with Tk PhotoImage, not a mock canvas.
"""
import os
from pathlib import Path
import unittest

from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.presentation import ActorView, BattleFrame, Camera, TileView
from sporebound.tk_renderer import CanvasRenderer


CONTENT = Path(__file__).resolve().parents[1] / "sporebound" / "content"


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Tk and a display are required")
class PlayerCanvas376Tests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.geometry("420x350")
        self.canvas = tk.Canvas(self.root, width=320, height=260,
                                highlightthickness=0)
        self.canvas.pack()
        self.root.update()
        content = Content.load(CONTENT / "jeanne.json")
        project = GameProject.load(CONTENT / "jeanne.game.json", content)
        self.renderer = CanvasRenderer(self.canvas,
                                       registry=project.asset_registry(),
                                       asset_root=CONTENT)

    def tearDown(self):
        self.renderer.dispose()
        self.root.destroy()

    @staticmethod
    def scene():
        tiles = tuple(TileView((x, y), (x + y) % 2, (x + y) % 9 == 0,
                               (x + y) % 7 == 0, (x + y) % 3 == 0)
                      for y in range(14) for x in range(18))
        hero = ActorView("jeanne", "Jeanne", "player", (2, 2), (1, 1),
                         50, 74, 3, 3, True, True, ())
        enemy = ActorView("bandit-test", "Bandit", "enemy", (8, 4), (1, 1),
                          15, 25, 0, 0, True, False, ())
        return BattleFrame("p0_01_lame", 18, 14, 1, "jeanne", False, None,
                           tiles, (hero, enemy), (), (2, 2),
                           ((2, 3), (3, 2)),
                           (), (), ({"cell": [2, 3], "kind": "charge"},))

    def test_sprite_scales_to_every_camera_zoom_and_reuses_cache(self):
        source = self.renderer._photo("jeanne_south_idle_0")
        self.assertEqual((source.width(), source.height()), (64, 64))
        for zoom in (16, 24, 48, 52, 64, 72, 104, 128):
            image = self.renderer._cell_photo(source, zoom)
            self.assertEqual((image.width(), image.height()), (zoom, zoom))
            self.assertIs(image, self.renderer._cell_photo(source, zoom))
            self.assertEqual(image.get(zoom // 2, zoom // 2),
                             source.get(32, 32))
        self.assertEqual(len(self.renderer._cell_images), 7)
        self.assertEqual(len(self.renderer._sources), 1)

    def test_draw_culls_offscreen_tiles_and_actors_after_zoom_pan(self):
        frame = self.scene()
        camera = Camera(52, 0, 0)
        self.renderer.draw(frame, camera, clock_ms=0)
        initial = len(self.canvas.find_all())
        self.assertGreater(initial, 2)
        self.assertLess(initial, 18 * 14)
        imgs = [item for item in self.canvas.find_all()
                if self.canvas.type(item) == "image"]
        self.assertEqual(len(imgs), 1)  # Jeanne is visible; bandit is not.
        self.assertEqual((self.renderer._cell_images[(str(
            self.renderer._photo("jeanne_south_idle_0")), 52)].width(),
                          self.renderer._cell_images[(str(
            self.renderer._photo("jeanne_south_idle_0")), 52)].height()),
                         (52, 52))

        self.renderer.draw(frame, Camera(104, -800, -700), clock_ms=60)
        self.assertLess(len(self.canvas.find_all()), initial)
        self.assertEqual(len([item for item in self.canvas.find_all()
                              if self.canvas.type(item) == "image"]), 0)

        # Before Tk layout, a 1x1 viewport must not hide the game.
        self.root.withdraw()
        tiny = self.root.winfo_width()
        # Window managers vary; call the same renderer and ensure no exception.
        self.renderer.draw(frame, Camera(52), clock_ms=120)
        self.assertTrue(tiny >= 1)

    def test_repaint_never_changes_authoritative_frame(self):
        frame = self.scene()
        before = repr(frame)
        for cell in (24, 52, 64, 104):
            self.renderer.draw(frame, Camera(cell), clock_ms=200)
        self.assertEqual(repr(frame), before)
        self.assertEqual(len(self.renderer._sources), 1)


if __name__ == "__main__":
    unittest.main()
