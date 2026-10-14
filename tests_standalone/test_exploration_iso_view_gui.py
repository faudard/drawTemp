"""Real Tk regression for Jeanne's initial exploration in shared isometric view."""
import os
from pathlib import Path
import unittest

from sporebound.exploration_iso_view import IsoExplorationCanvas
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk and a virtual/physical display")
class ExplorationIsoGUITests(unittest.TestCase):
    def test_jeanne_fields_render_png_and_pick_adjacent_diamond(self):
        import tkinter as tk

        root = tk.Tk()
        root.geometry("740x580+0+0")
        canvas = tk.Canvas(root, width=690, height=495)
        canvas.pack()
        try:
            root.update()
            content = Content.load(ROOT / "sporebound/content/jeanne.json")
            project = GameProject.load(
                ROOT / "sporebound/content/jeanne.game.json", content)
            session = GameSession.new(content, project, "jeanne")
            stage = session.exploration_state()
            view = IsoExplorationCanvas(canvas)
            view.draw(stage)
            root.update()

            self.assertTrue(canvas.find_withtag("iso_tile_0_0"))
            self.assertTrue(canvas.find_withtag("iso_actor_sprite"))
            self.assertTrue(canvas.find_withtag("exploration_hotspot"))
            self.assertEqual(len(canvas.find_withtag("exploration_hotspot")),
                             5 * len(stage["interactions"]))
            self.assertEqual(len(canvas.find_withtag("exploration_atmosphere")), 28)
            self.assertTrue(canvas.find_withtag("exploration_hero_focus"))
            x, y = stage["position"]
            neighbor = (x + 1, y)
            self.assertFalse(view.geometry.board.tile(neighbor).blocked)
            cx, cy = view._center(neighbor)
            self.assertEqual(view.hit_test(cx, cy), neighbor)
            self.assertIsNone(view.hit_test(-500, -500))
            self.assertEqual(session.exploration_state()["position"],
                             stage["position"])
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
