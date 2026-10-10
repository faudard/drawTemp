"""Real Tk smoke of the new GameSession-based player (xvfb)."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.player_app import launch
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.player_controller import PlayerController


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk and a display")
class Player26GuiTests(unittest.TestCase):
    def test_new_game_command_checkpoint_and_resume(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            profile = Path(folder) / "test.game.json"
            errors = []
            def drive(root):
                try:
                    root.report_callback_exception = lambda *args: errors.append(args)
                    root.update()
                    def button(label):
                        return next(w for w in descendants(root)
                                    if isinstance(w, ttk.Button) and w.cget("text") == label)
                    button("Nouvelle partie").invoke()
                    root.update()
                    next(w for w in descendants(root)
                         if isinstance(w, ttk.Button) and "Escarmouche du jardin"
                         in w.cget("text")).invoke()
                    root.update()
                    self.assertTrue(any(isinstance(w, tk.Canvas) for w in descendants(root)))
                    button("Sauvegarder").invoke()
                    root.update()
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.messagebox.showerror") as errors_box:
                launch(DEFAULT_CONTENT, profile_path=profile)
                errors_box.assert_not_called()
            content = Content.load(DEFAULT_CONTENT)
            project = GameProject.load(Path(DEFAULT_CONTENT).with_suffix(".game.json"), content)
            player = PlayerController(content, project, profile)
            resumed = player.load_game("main", 1)
            self.assertEqual(resumed.mode, "battle")


if __name__ == "__main__":
    unittest.main()
