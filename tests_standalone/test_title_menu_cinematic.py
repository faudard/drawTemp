"""R7: rendered six-card cinematic Player menu and safe controller wiring."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.title_menu_cinematic import CinematicTitleMenu, title_geometry


class TitleMenuGeometryTests(unittest.TestCase):
    def test_bounded_layout_and_nonoverlapping_actions(self):
        for width, height in ((800, 580), (1024, 768), (1160, 820), (1672, 914), (1920, 1080)):
            with self.subTest(size=(width, height)):
                layout = title_geometry(width, height)
                self.assertEqual(len(layout["cards"]), 6)
                for index, (x0, y0, x1, y1) in enumerate(layout["cards"]):
                    self.assertGreaterEqual(x0, 0)
                    self.assertGreaterEqual(y0, 0)
                    self.assertLessEqual(x1, width)
                    self.assertLessEqual(y1, layout["footer_y"])
                    self.assertGreater(x1-x0, 280)
                    self.assertGreater(y1-y0, 42)
                    if index:
                        self.assertGreater(y0, layout["cards"][index-1][3])
                self.assertLess(layout["campaign"][2], layout["menu_x"])
                self.assertLessEqual(layout["footer_y"] + layout["footer_height"], height)

    def test_packaged_art_is_present(self):
        from importlib.resources import files
        image = files("sporebound").joinpath(
            "content", "art", "jeanne", "jeanne_menu_stage.jpg")
        self.assertTrue(image.is_file())


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1", "Requires Tk display")
class TitleMenuCinematicGuiTests(unittest.TestCase):
    def test_menu_cards_are_live_and_do_not_mutate_game(self):
        from sporebound.__main__ import DEFAULT_CONTENT
        from sporebound.player_app import PlayerApplication
        with TemporaryDirectory() as directory:
            app = PlayerApplication(DEFAULT_CONTENT,
                                    profile_path=Path(directory) / "player.profile")
            try:
                app.root.update()
                menu = app._title_menu
                self.assertIsInstance(menu, CinematicTitleMenu)
                self.assertIsNone(app.player.session)
                self.assertEqual(menu.continue_button["state"], "disabled")
                self.assertEqual(len(menu._hitboxes), 10)
                self.assertEqual(len(menu.ACTIONS), 6)

                def click(tag):
                    box = menu._hitboxes[tag]
                    x = int((box[0] + box[2])/2)
                    y = int((box[1] + box[3])/2)
                    menu.canvas.event_generate("<Motion>", x=x, y=y)
                    menu.canvas.event_generate("<Button-1>", x=x, y=y)
                    app.root.update()

                for key in ("load", "campaign", "advanced", "credits", "help"):
                    with self.subTest(key=key):
                        click(key)
                        self.assertIsNotNone(menu.overlay)
                        self.assertIsNone(app.player.session)
                        menu._close_overlay()
                        app.root.update()
                old = menu._selection_index
                menu._move_selection(1)
                self.assertNotEqual(old, menu._selection_index)
                self.assertIsNone(app.player.session)
            finally:
                app.close()

    def test_jeanne_art_and_high_contrast_survive_resize(self):
        from sporebound.player_app import PlayerApplication
        root = Path(__file__).resolve().parents[1]
        content = root / "sporebound" / "content" / "jeanne.json"
        project = root / "sporebound" / "content" / "jeanne.game.json"
        with TemporaryDirectory() as directory:
            app = PlayerApplication(content, project,
                                    profile_path=Path(directory) / "player.profile")
            try:
                app.root.update()
                menu = app._title_menu
                self.assertIsInstance(menu, CinematicTitleMenu)
                from importlib.util import find_spec
                if find_spec("PIL") is not None:
                    self.assertIsNotNone(menu._stage_path)
                    self.assertTrue(menu._stage_path.is_file())
                else:
                    self.assertIsNotNone(menu._backdrop_native)
                for size in ("800x580", "1160x820"):
                    app.root.geometry(size)
                    app.root.update()
                    self.assertEqual(len(menu._hitboxes), 10)
                    self.assertIsNone(app.player.session)
                app.high_contrast.set(True)
                app.title_screen()
                app.root.update()
                self.assertTrue(app._title_menu.contrast)
                self.assertIsNone(app.player.session)
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()