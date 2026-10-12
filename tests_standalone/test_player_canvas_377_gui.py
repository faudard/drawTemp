"""3.7.7 — Tk background caching must not hide authoritative overlays."""
import os
from dataclasses import replace
from pathlib import Path
import unittest

from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.presentation import ActorView, BattleFrame, Camera, TileView
from sporebound.tk_renderer import CanvasRenderer


CONTENT = Path(__file__).resolve().parents[1] / "sporebound" / "content"


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "A live Tk/Xvfb display is required")
class PlayerTerrainLayer377Tests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.geometry("440x360")
        self.canvas = tk.Canvas(self.root, width=360, height=280,
                                highlightthickness=0)
        self.canvas.pack()
        self.root.update()
        content = Content.load(CONTENT / "jeanne.json")
        project = GameProject.load(CONTENT / "jeanne.game.json", content)
        self.renderer = CanvasRenderer(
            self.canvas, registry=project.asset_registry(), asset_root=CONTENT)
        self.camera = Camera(52, 0, 0)

    def tearDown(self):
        self.renderer.dispose()
        self.root.destroy()

    def frame(self):
        tiles = tuple(TileView((x, y), (x + y) % 3, False, 0, (x + y) % 2)
                      for y in range(8) for x in range(12))
        hero = ActorView("jeanne", "Jeanne", "player", (2, 2),
                         (1, 1), 55, 74, 4, 4, True, True, ())
        return BattleFrame(
            "p0_01_lame", 12, 8, 1, "jeanne", False, None,
            tiles, (hero,), (), (2, 2), ((2, 3),), (), (),
            ({"cell": [3, 2], "kind": "cast"},))

    def test_idle_redraw_reuses_static_and_tactical_overlay_items(self):
        frame = self.frame()
        self.renderer.draw(frame, self.camera, clock_ms=0)
        terrain = self.canvas.find_withtag("terrain")
        dynamic = self.canvas.find_withtag("dynamic")
        self.assertGreater(len(terrain), 20)
        self.assertTrue(dynamic)
        self.assertFalse(set(terrain) & set(dynamic))
        self.assertEqual(self.renderer._terrain_rebuilds, 1)
        self.assertEqual(self.renderer._overlay_rebuilds, 1)

        for timestamp in (60, 120, 180, 240):
            self.renderer.draw(frame, self.camera, clock_ms=timestamp)
            self.assertEqual(self.canvas.find_withtag("terrain"), terrain)
            self.assertEqual(self.renderer._terrain_rebuilds, 1)
            self.assertEqual(self.canvas.find_withtag("dynamic"), dynamic)
            self.assertEqual(self.renderer._overlay_rebuilds, 1)
            self.assertFalse(set(terrain) & set(self.canvas.find_withtag("dynamic")))

    def test_live_threat_selection_and_hp_refresh_without_terrain_repaint(self):
        frame = self.frame()
        self.renderer.draw(frame, self.camera, clock_ms=0)
        terrain = self.canvas.find_withtag("terrain")
        changed = replace(
            frame, selected=(3, 2), reachable=((3, 3),),
            danger=({"cell": [2, 3], "kind": "charge"},),
            actors=(replace(frame.actors[0], hp=16, pos=(3, 2)),))
        self.renderer.draw(changed, self.camera, clock_ms=60)
        self.assertEqual(self.renderer._terrain_rebuilds, 1)
        self.assertEqual(self.canvas.find_withtag("terrain"), terrain)
        self.assertTrue(any(
            self.canvas.itemcget(item, "outline") == "#f5ae60"
            for item in self.canvas.find_withtag("dynamic")
            if self.canvas.type(item) == "rectangle"))
        self.assertFalse(any(
            self.canvas.itemcget(item, "outline") == "#c69df8"
            for item in self.canvas.find_withtag("dynamic")
            if self.canvas.type(item) == "rectangle"))

    def test_zoom_pan_resize_tile_edit_and_none_invalidate_background(self):
        frame = self.frame()
        self.renderer.draw(frame, self.camera)
        for camera in (self.camera.panned(-42, 17),
                       self.camera.zoomed(2, (120, 80))):
            before = self.renderer._terrain_rebuilds
            self.renderer.draw(frame, camera)
            self.assertEqual(self.renderer._terrain_rebuilds, before + 1)
        newer = replace(frame, tiles=(
            replace(frame.tiles[0], blocked=True), *frame.tiles[1:]))
        before = self.renderer._terrain_rebuilds
        self.renderer.draw(newer, self.camera)
        self.assertEqual(self.renderer._terrain_rebuilds, before + 1)
        self.canvas.configure(width=290, height=250)
        self.root.update()
        before = self.renderer._terrain_rebuilds
        self.renderer.draw(newer, self.camera)
        self.assertEqual(self.renderer._terrain_rebuilds, before + 1)

        self.renderer.draw(None, self.camera)
        self.assertEqual(self.canvas.find_all(), ())
        self.assertIsNone(self.renderer._terrain_key)
        self.renderer.draw(newer, self.camera)
        self.assertEqual(self.renderer._terrain_rebuilds, before + 2)


if __name__ == "__main__":
    unittest.main()
