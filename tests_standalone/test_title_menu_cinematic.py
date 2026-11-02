"""R7: rendered six-card cinematic Player menu and safe controller wiring."""
import os
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.title_menu_cinematic import (
    CinematicTitleMenu, render_title_background, title_geometry,
)


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

    @unittest.skipUnless(find_spec("PIL") is not None,
                         "Pillow is needed for rendered image checks")
    def test_pillow_cover_and_continuous_fade(self):
        from PIL import Image

        source = Image.new("RGB", (640, 900), (224, 130, 72))
        for width, height in ((800, 580), (1160, 820),
                              (1595, 933), (1920, 1080)):
            with self.subTest(size=(width, height)):
                layout = title_geometry(width, height)
                scenic_width = round(width * (.69 if layout["compact"] else .73))
                backdrop = render_title_background(
                    source, width, height, layout["menu_x"], scenic_width)
                self.assertEqual(backdrop.size, (width, height))
                self.assertEqual(backdrop.getpixel((0, height // 2)),
                                 (224, 130, 72))
                self.assertEqual(backdrop.getpixel((width - 1, height // 2)),
                                 (15, 27, 42))
                start = round(layout["menu_x"] * .77)
                end = round(layout["menu_x"] + 38)
                midpoint = (start + end) // 2
                channel_values = [
                    backdrop.getpixel((x, height // 2))[0]
                    for x in (start, midpoint, end)]
                self.assertGreater(channel_values[0], channel_values[1])
                self.assertGreater(channel_values[1], channel_values[2])

    @unittest.skipUnless(find_spec("PIL") is not None,
                         "Pillow is needed for rendered image checks")
    def test_pillow_rejects_invalid_dimensions(self):
        from PIL import Image
        with self.assertRaises(ValueError):
            render_title_background(Image.new("RGB", (64, 64)), 0, 600,
                                    300, 350)

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

    def test_missing_pillow_uses_unpixelated_vector_fallback(self):
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
                # Simulate an uninstalled runtime: do not use any decoded image
                # or the legacy native PhotoImage even if Pillow is present.
                menu._stage_source = None
                menu._stage_path = False
                menu._backdrop_source = None
                menu._stage_photo = None
                menu._stage_size = None
                for size in ("800x580", "1595x933"):
                    with self.subTest(size=size):
                        app.root.geometry(size)
                        app.root.update()
                        menu.paint(menu.canvas.winfo_width(),
                                   menu.canvas.winfo_height())
                        self.assertIsNone(menu._stage_photo)
                        items = menu.canvas.find_withtag("art")
                        self.assertGreater(len(items), 0)
                        self.assertFalse(any(menu.canvas.type(item) == "image"
                                             for item in items))
                        self.assertEqual(len(menu._hitboxes), 10)
            finally:
                app.close()

    def test_long_card_titles_stay_within_their_border(self):
        from sporebound.player_app import PlayerApplication
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            app = PlayerApplication(
                root / "sporebound" / "content" / "jeanne.json",
                root / "sporebound" / "content" / "jeanne.game.json",
                profile_path=Path(directory) / "player.profile")
            try:
                app.root.update()
                menu = app._title_menu
                for size in ("800x580", "1160x820", "1595x933"):
                    with self.subTest(size=size):
                        app.root.geometry(size)
                        app.root.update()
                        for key, label, *_ in menu.ACTIONS:
                            rect = menu._hitboxes[key]
                            titles = [
                                item for item in menu.canvas.find_withtag("title_card_" + key)
                                if menu.canvas.type(item) == "text"
                                and menu.canvas.itemcget(item, "text") == label]
                            self.assertEqual(len(titles), 1)
                            bounds = menu.canvas.bbox(titles[0])
                            self.assertIsNotNone(bounds)
                            self.assertLessEqual(bounds[2], rect[2] - 27)
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
                if find_spec("PIL") is not None:
                    self.assertIsNotNone(menu._stage_path)
                    self.assertEqual(menu._stage_path.name, "jeanne_menu_backdrop.png")
                    self.assertIsNotNone(menu._stage_photo)
                else:
                    self.assertIsNone(menu._stage_photo)  # vector-only fallback
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