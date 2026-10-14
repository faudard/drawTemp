"""Title menu regression gates: no save mutation from navigation."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.title_menu import has_save


class FakePlayer:
    def __init__(self, root):
        self.root = Path(root)

    def path_for(self, cid, slot):
        return self.root / cid / ("slot_%d.json" % slot)

    def long_path_for(self, cid, slot):
        return self.root / cid / ("slot_%d.long.json" % slot)


class TitleArtworkTests(unittest.TestCase):
    def test_jeanne_panorama_is_bundled(self):
        from importlib.resources import files

        backdrop = files("sporebound").joinpath(
            "content", "art", "jeanne", "jeanne_menu_backdrop.png")
        self.assertTrue(backdrop.is_file())



class TitleSlotTests(unittest.TestCase):
    def test_uninitialized_and_backup_only_slots(self):
        with TemporaryDirectory() as directory:
            player = FakePlayer(directory)
            normal = player.path_for("jeanne", 1)
            recovery = normal.with_name(normal.name + ".bak")
            recovery.parent.mkdir(parents=True)
            self.assertFalse(has_save(player, "jeanne", 1))
            self.assertFalse(has_save(player, "jeanne", 1, long_mode=True))
            recovery.write_text("backup", encoding="utf-8")
            self.assertTrue(has_save(player, "jeanne", 1))
            self.assertFalse(has_save(player, "jeanne", 1, long_mode=True))
            long_file = player.long_path_for("jeanne", 1)
            long_file.write_text("long", encoding="utf-8")
            self.assertTrue(has_save(player, "jeanne", 1, long_mode=True))
            self.assertFalse(has_save(player, "jeanne", 2))


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a Tk display")
class TitleMenuGuiTests(unittest.TestCase):
    def test_jeanne_background_and_high_contrast(self):
        from sporebound.player_app import PlayerApplication

        root = Path(__file__).resolve().parents[1]
        content = root / "sporebound" / "content" / "jeanne.json"
        project = root / "sporebound" / "content" / "jeanne.game.json"
        with TemporaryDirectory() as directory:
            app = PlayerApplication(
                content, project, profile_path=Path(directory) / "player.profile")
            try:
                app.root.update()
                menu = app._title_menu
                self.assertIsNotNone(menu._backdrop_path)
                self.assertTrue(menu._backdrop_path.is_file())
                self.assertTrue(
                    menu._backdrop_source is not None or
                    menu._backdrop_native is not None)
                self.assertIsNone(app.player.session)
                app.high_contrast.set(True)
                app.title_screen()
                app.root.update()
                self.assertTrue(app._title_menu.contrast)
                self.assertEqual(app.presentation.screen, "title")
            finally:
                app.close()

    def test_navigation_and_advanced_tools_do_not_autorun(self):
        import tkinter as tk
        from sporebound.__main__ import DEFAULT_CONTENT
        from sporebound.player_app import PlayerApplication

        with TemporaryDirectory() as directory:
            app = PlayerApplication(
                DEFAULT_CONTENT, profile_path=Path(directory) / "player.profile")
            try:
                app.root.update()
                menu = app._title_menu
                self.assertEqual(app.presentation.screen, "title")
                self.assertIsNone(menu.overlay)
                self.assertEqual(str(menu.continue_button["state"]), "disabled")
                self.assertEqual(menu.new_button["text"], "NOUVELLE PARTIE")
                self.assertIsNone(app.player.session)

                menu.open_selection()
                app.root.update_idletasks()
                self.assertIsNotNone(menu.overlay)
                self.assertIsNone(app.player.session)
                menu._close_overlay()

                menu.open_advanced()
                app.root.update_idletasks()
                labels = [widget.cget("text") for widget in menu.overlay.winfo_children()
                          if isinstance(widget, tk.Button)]
                self.assertTrue(any("Migrer" in label for label in labels))
                self.assertIsNone(app.player.session)
                menu._close_overlay()

                app.player.new_game("main", 1)
                app.title_screen()
                app.root.update()
                self.assertEqual(str(app._title_menu.continue_button["state"]), "normal")
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
