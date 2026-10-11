"""3.7.5: prove actual Tk image decoding and atlas clipping under Xvfb."""
import os
from pathlib import Path
import unittest

from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.presentation import ActorView, BattleFrame, Camera
from sporebound.tk_renderer import CanvasRenderer


CONTENT = Path(__file__).resolve().parents[1] / "sporebound" / "content"


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1", "GUI smoke opt-in")
class JeanneAtlasTkTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.withdraw()
        self.canvas = tk.Canvas(self.root, width=500, height=400)
        self.canvas.pack()
        content = Content.load(CONTENT / "jeanne.json")
        registry = GameProject.load(
            CONTENT / "jeanne.game.json", content).asset_registry()
        self.renderer = CanvasRenderer(self.canvas, registry=registry,
                                       asset_root=CONTENT)

    def tearDown(self):
        self.renderer.dispose()
        self.root.destroy()

    def test_all_directions_reuse_atlas_source(self):
        for direction in ("south", "north", "east", "west"):
            for state in ("idle", "move", "attack", "hit", "defeat"):
                photo = self.renderer._photo(f"jeanne_{direction}_{state}_0")
                self.assertIsNotNone(photo, (direction, state))
                self.assertEqual((photo.width(), photo.height()), (64, 64))
        self.assertEqual(len(self.renderer._sources), 1)
        portrait = self.renderer.image("portrait", "Jeanne")
        self.assertIsNotNone(portrait)
        self.assertEqual((portrait.width(), portrait.height()), (64, 64))
        self.assertEqual(len(self.renderer._sources), 2)

    def test_player_canvas_draws_real_sprite_and_health_bar(self):
        actor = ActorView("jeanne", "Jeanne", "player", (2, 2), (1, 1),
                          50, 74, 3, 3, True, True, ())
        frame = BattleFrame("p0_01_lame", 6, 6, 1, "jeanne", False, None,
                            (), (actor,), (), None, (), (), ())
        self.renderer.draw(frame, Camera(64, 0, 0))
        self.assertGreater(len(self.canvas.find_all()), 1)


if __name__ == "__main__":
    unittest.main()
