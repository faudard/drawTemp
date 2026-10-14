"""Player exploration HUD, pause and save shortcut regression gates."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock
import unittest

from sporebound.exploration_iso_view import exploration_iso_cell_size
from sporebound.player_app import PlayerApplication


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "sporebound/content/jeanne.json"
PROJECT = ROOT / "sporebound/content/jeanne.game.json"


class PlayerShortcutTests(TestCase):
    def test_shortcuts_only_run_during_play(self):
        app = PlayerApplication.__new__(PlayerApplication)
        app.player = SimpleNamespace(session=object())
        app.presentation = SimpleNamespace(screen="title")
        app._safe = mock.Mock()
        action = mock.Mock()
        self.assertIsNone(app._game_shortcut(action))
        app._safe.assert_not_called()
        app.presentation.screen = "campaign"
        self.assertEqual(app._game_shortcut(action), "break")
        app._safe.assert_called_once_with(action)
        app._safe.reset_mock()
        app.presentation.screen = "battle"
        self.assertIsNone(app._game_shortcut(action, campaign_only=True))
        app._safe.assert_not_called()

    def test_quick_load_uses_actual_active_slot_and_requires_confirmation(self):
        app = PlayerApplication.__new__(PlayerApplication)
        app.player = SimpleNamespace(campaign_id="jeanne", slot=2, long_mode=True)
        app.campaign_var = mock.Mock()
        app.slot_var = mock.Mock()
        app.long_save_var = mock.Mock()
        app._load_game = mock.Mock()
        app.messagebox = SimpleNamespace(askyesno=mock.Mock(return_value=False))
        app._quick_load()
        app._load_game.assert_not_called()
        app.messagebox.askyesno.return_value = True
        app._quick_load()
        app.campaign_var.set.assert_called_once_with("jeanne")
        app.slot_var.set.assert_called_once_with("2")
        app.long_save_var.set.assert_called_once_with(True)
        app._load_game.assert_called_once_with()

    def test_fullscreen_iso_cell_size_adapts_and_is_bounded(self):
        stage = {"width": 10, "height": 7}
        small = exploration_iso_cell_size(stage, (690, 495))
        large = exploration_iso_cell_size(stage, (1600, 900))
        self.assertGreaterEqual(small, 28)
        self.assertGreater(large, small)
        self.assertLessEqual(large, 88)
        self.assertEqual(exploration_iso_cell_size(stage, (8000, 8000)), 88)


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk and a physical/virtual display")
class ImmersiveExplorationGuiTests(TestCase):
    def test_jeanne_exploration_is_only_map_with_pause_and_quicksave(self):
        import tkinter as tk
        from tkinter import ttk

        with TemporaryDirectory() as directory:
            app = PlayerApplication(
                CONTENT, PROJECT, profile_path=Path(directory) / "jeanne.profile")
            try:
                app.player.new_game("jeanne", 1)
                app.show()
                app.root.update()
                self.assertEqual(app.presentation.screen, "campaign")
                self.assertIsInstance(app.canvas, tk.Canvas)
                self.assertEqual(app.view.cget("padding"), (0, 0, 0, 0))
                self.assertFalse(any(isinstance(widget, ttk.Button)
                                     for widget in app.view.winfo_children()))
                self.assertIsNotNone(app.canvas.iso_scene)
                self.assertGreater(app.canvas.iso_scene.geometry.cell_size, 28)

                app._handle_escape()
                app.root.update()
                self.assertIsNotNone(app._pause_dialog)
                self.assertTrue(app._pause_dialog.winfo_exists())
                app._close_pause()
                self.assertIsNone(app._pause_dialog)
                self.assertEqual(app.presentation.screen, "campaign")

                app._game_shortcut(app._quick_save)
                path = app.player.path_for("jeanne", 1)
                self.assertTrue(path.is_file())
                self.assertIn("sauvegardée", app._explore_feedback)
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
