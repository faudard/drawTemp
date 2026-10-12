"""3.7.9 — live Tk overlay reuse, priority and invalidation regressions."""
import os
from dataclasses import replace
from pathlib import Path
import unittest

from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.presentation import ActorView, BattleFrame, Camera, ObjectView, TileView
from sporebound.tk_renderer import CanvasRenderer


CONTENT = Path(__file__).resolve().parents[1] / "sporebound" / "content"


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires live Tk/Xvfb")
class PlayerOverlay379GUITests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.geometry("460x380")
        self.canvas = tk.Canvas(self.root, width=400, height=300,
                                highlightthickness=0)
        self.canvas.pack()
        self.root.update()
        content = Content.load(CONTENT / "jeanne.json")
        project = GameProject.load(CONTENT / "jeanne.game.json", content)
        self.renderer = CanvasRenderer(self.canvas,
                                       registry=project.asset_registry(),
                                       asset_root=CONTENT)
        self.camera = Camera(52, 0, 0)

    def tearDown(self):
        self.renderer.dispose()
        self.root.destroy()

    @staticmethod
    def frame():
        tiles = tuple(TileView((x, y), 0, False, 0, 0)
                      for y in range(8) for x in range(12))
        jeanne = ActorView("jeanne", "Jeanne", "player", (2, 2), (1, 1),
                           60, 74, 4, 4, True, True, ())
        return BattleFrame(
            "p0_01_lame", 12, 8, 1, "jeanne", False, None,
            tiles, (jeanne,), (ObjectView("porte", "door", (4, 3), False),),
            (2, 2), ((3, 2),), (), (),
            ({"cell": [2, 3], "kind": "charge"},))

    def outlines(self, color):
        return [item for item in self.canvas.find_withtag("dynamic")
                if self.canvas.type(item) == "rectangle"
                and self.canvas.itemcget(item, "outline") == color]

    def test_static_overlay_survives_idle_animation_and_health_updates(self):
        frame = self.frame()
        self.renderer.draw(frame, self.camera, clock_ms=0)
        overlay = self.canvas.find_withtag("dynamic")
        actor = self.canvas.find_withtag("actor")
        self.assertTrue(overlay)
        self.assertTrue(actor)
        self.assertEqual(self.renderer._overlay_rebuilds, 1)
        for tick in (30, 60, 120, 180):
            self.renderer.draw(frame, self.camera, clock_ms=tick)
            self.assertEqual(overlay, self.canvas.find_withtag("dynamic"))
            self.assertEqual(1, self.renderer._overlay_rebuilds)
        frame_hp = replace(frame, actors=(
            replace(frame.actors[0], hp=15),))
        self.renderer.draw(frame_hp, self.camera, clock_ms=240)
        self.assertEqual(overlay, self.canvas.find_withtag("dynamic"))
        self.assertEqual(1, self.renderer._overlay_rebuilds)
        self.assertTrue(self.outlines("#f5ae60"))

    def test_threat_priority_selection_reachable_and_objects_invalidate(self):
        frame = self.frame()
        self.renderer.draw(frame, self.camera)
        old = self.canvas.find_withtag("dynamic")
        changes = replace(
            frame, selected=(3, 3), reachable=((3, 3), (4, 3)),
            danger=({"cell": [2, 3], "kind": "charge"},
                    {"cell": [2, 3], "kind": "cast"}),
            objects=(replace(frame.objects[0], opened=True),))
        self.renderer.draw(changes, self.camera)
        self.assertEqual(self.renderer._terrain_rebuilds, 1)
        self.assertEqual(self.renderer._overlay_rebuilds, 2)
        self.assertNotEqual(old, self.canvas.find_withtag("dynamic"))
        self.assertFalse(self.outlines("#f5ae60"))
        self.assertTrue(self.outlines("#c69df8"))
        self.assertTrue(self.outlines("#ffe78a"))
        self.assertTrue(any(
            self.canvas.itemcget(item, "fill") == "#47b9a4"
            for item in self.canvas.find_withtag("dynamic")
            if self.canvas.type(item) == "rectangle"))
        self.renderer.draw(frame, self.camera)
        self.assertTrue(self.outlines("#f5ae60"))
        self.assertFalse(self.outlines("#c69df8"))
        self.assertEqual(self.renderer._overlay_rebuilds, 3)

    def test_reordered_or_irrelevant_threat_metadata_does_not_redraw(self):
        frame = self.frame()
        self.renderer.draw(frame, self.camera)
        prev = self.canvas.find_withtag("dynamic")
        expanded = replace(
            frame, danger=(
                {"cell": [2, 3], "kind": "hazard", "source": "weather"},
                {"cell": [2, 3], "kind": "charge", "source": "bandit"}))
        self.renderer.draw(expanded, self.camera)
        self.assertEqual(prev, self.canvas.find_withtag("dynamic"))
        self.assertEqual(self.renderer._overlay_rebuilds, 1)

    def test_zoom_pan_tile_resize_and_reset_invalidate(self):
        frame = self.frame()
        self.renderer.draw(frame, self.camera)
        for camera in (self.camera.zoomed(1, (100, 80)),
                       self.camera.panned(15, -24)):
            old = self.renderer._overlay_rebuilds
            self.renderer.draw(frame, camera)
            self.assertEqual(old + 1, self.renderer._overlay_rebuilds)
        old = self.renderer._overlay_rebuilds
        frame = replace(frame, tiles=(
            replace(frame.tiles[0], blocked=True), *frame.tiles[1:]))
        self.renderer.draw(frame, self.camera)
        self.assertEqual(old + 1, self.renderer._overlay_rebuilds)
        old = self.renderer._overlay_rebuilds
        self.canvas.configure(width=320, height=240)
        self.root.update()
        self.renderer.draw(frame, self.camera)
        self.assertEqual(old + 1, self.renderer._overlay_rebuilds)
        self.renderer.draw(None, self.camera)
        self.assertEqual(self.canvas.find_all(), ())
        self.assertIsNone(self.renderer._overlay_key)
        self.renderer.draw(frame, self.camera)
        self.assertEqual(old + 2, self.renderer._overlay_rebuilds)

    def test_result_stays_top_when_same_frame_redrawn(self):
        frame = replace(self.frame(), result="victory")
        self.renderer.draw(frame, self.camera)
        top = self.canvas.find_all()[-1]
        self.assertEqual(self.canvas.itemcget(top, "text"), "VICTORY")
        for tick in (60, 120, 240):
            self.renderer.draw(frame, self.camera, clock_ms=tick)
            self.assertEqual(self.canvas.find_all()[-1], top)
        changed = replace(frame, result=None)
        self.renderer.draw(changed, self.camera)
        self.assertEqual(self.canvas.find_withtag("result"), ())
        self.renderer.draw(frame, self.camera)
        self.assertEqual(self.canvas.itemcget(self.canvas.find_all()[-1],
                                               "text"), "VICTORY")


if __name__ == "__main__":
    unittest.main()
