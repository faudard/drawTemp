"""3.7.8 — Verify real Tk actor item reuse and authoritative updates."""
import os
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.presentation import ActorView, BattleFrame, Camera, TileView
from sporebound.tk_renderer import CanvasRenderer
from sporebound.visual_motion import ActorPose

CONTENT = Path(__file__).resolve().parents[1] / "sporebound" / "content"


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a real Tk/Xvfb display")
class IncrementalActor378GUITests(unittest.TestCase):
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
        self.renderer = CanvasRenderer(
            self.canvas, registry=project.asset_registry(), asset_root=CONTENT)
        self.camera = Camera(52, 0, 0)

    def tearDown(self):
        self.renderer.dispose()
        self.root.destroy()

    def frame(self):
        tiles = tuple(TileView((x, y), 0, False, 0, 0)
                      for y in range(8) for x in range(12))
        hero = ActorView("jeanne", "Jeanne", "player", (2, 2), (1, 1),
                         65, 74, 4, 4, True, True, ())
        foe = ActorView("guard", "Garde", "enemy", (4, 3), (1, 1),
                        20, 20, 0, 0, True, False, ())
        return BattleFrame("p0_01_lame", 12, 8, 1, "jeanne", False, None,
                           tiles, (hero, foe), (), (2, 2), ((3, 2),),
                           (), (), ({"cell": [2, 3], "kind": "cast"},))

    def test_static_actors_keep_item_ids_on_idle_frames(self):
        frame = self.frame()
        self.renderer.draw(frame, self.camera, clock_ms=0)
        actor_ids = self.canvas.find_withtag("actor")
        self.assertGreaterEqual(len(actor_ids), 9)
        self.assertEqual(len(self.renderer._actor_items), 2)
        self.assertEqual(self.renderer._actor_creations, 2)
        for tick in range(1, 5):
            self.renderer.draw(frame, self.camera, clock_ms=tick * 60)
            self.assertEqual(self.canvas.find_withtag("actor"), actor_ids)
            self.assertEqual(self.renderer._actor_creations, 2)
        self.assertEqual(self.renderer._actor_updates, 0)
        self.assertFalse(set(actor_ids) & set(self.canvas.find_withtag("dynamic")))

    def test_motion_hp_and_direction_update_same_sprite_canvas_item(self):
        frame = self.frame()
        self.renderer.draw(frame, self.camera, clock_ms=0)
        hero = self.renderer._actor_items["jeanne"]
        image_id = hero["ids"]["image"]
        health_id = hero["ids"]["health"]
        before = tuple(self.canvas.coords(image_id))
        moved = replace(frame, actors=(
            replace(frame.actors[0], hp=22, pos=(3, 2), active=False),
            frame.actors[1]))
        self.renderer.draw(
            moved, self.camera,
            poses={"jeanne": ActorPose(2.5, 2, "move", "east")},
            elapsed_ms=80, clock_ms=80)
        self.assertEqual(self.renderer._actor_items["jeanne"]["ids"]["image"],
                         image_id)
        self.assertNotEqual(tuple(self.canvas.coords(image_id)), before)
        self.assertEqual(self.canvas.itemcget(health_id, "fill"), "#66d48b")
        self.assertAlmostEqual(
            self.canvas.coords(health_id)[2],
            2.5 * 52 + 5 + (52 - 10) * 22 / 74)
        self.assertEqual(self.canvas.itemcget(hero["ids"]["active"], "state"),
                         "hidden")
        self.assertGreaterEqual(self.renderer._actor_updates, 1)
        self.assertEqual(self.renderer._actor_creations, 2)

    def test_offscreen_and_removed_actors_do_not_leave_canvas_ghosts(self):
        frame = self.frame()
        self.renderer.draw(frame, self.camera)
        gone_id = self.renderer._actor_items["guard"]["ids"]["oval"]
        offscreen = replace(frame, actors=(
            frame.actors[0], replace(frame.actors[1], pos=(10, 7))))
        self.renderer.draw(offscreen, self.camera)
        self.assertNotIn("guard", self.renderer._actor_items)
        self.assertNotIn(gone_id, self.canvas.find_all())
        self.renderer.draw(frame, self.camera)
        self.assertIn("guard", self.renderer._actor_items)
        self.assertNotEqual(
            self.renderer._actor_items["guard"]["ids"]["oval"], gone_id)
        self.renderer.draw(replace(frame, actors=(frame.actors[0],)), self.camera)
        self.assertNotIn("guard", self.renderer._actor_items)
        self.renderer.draw(None, self.camera)
        self.assertEqual(self.canvas.find_all(), ())
        self.assertEqual(self.renderer._actor_items, {})

    def test_vector_to_sprite_switch_reallocates_only_changed_actor(self):
        frame = self.frame()
        with patch.object(self.renderer, "_photo", return_value=None), \
             patch.object(self.renderer, "image", return_value=None):
            self.renderer.draw(frame, self.camera)
        old_hero = self.renderer._actor_items["jeanne"]["ids"]["oval"]
        old_guard = self.renderer._actor_items["guard"]["ids"]["oval"]
        self.renderer.draw(frame, self.camera)
        hero = self.renderer._actor_items["jeanne"]
        self.assertIn("image", hero["ids"])
        self.assertNotIn(old_hero, self.canvas.find_all())
        self.assertEqual(self.renderer._actor_items["guard"]["ids"]["oval"],
                         old_guard)

    def test_overlays_remain_under_actors_but_result_banner_is_on_top(self):
        frame = replace(self.frame(), result="victory")
        self.renderer.draw(frame, self.camera)
        actors = self.canvas.find_withtag("actor")
        self.assertTrue(actors)
        self.assertGreater(min(actors), 0)
        top = self.canvas.find_all()[-1]
        self.assertEqual(self.canvas.type(top), "text")
        self.assertEqual(self.canvas.itemcget(top, "text"), "VICTORY")
        self.assertNotIn(top, actors)


if __name__ == "__main__":
    unittest.main()
