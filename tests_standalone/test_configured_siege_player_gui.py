"""Xvfb: a siege authored into a .game.json starts and resumes in Player Tk."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.player_app import launch
from sporebound.siege_authoring import new_blueprint, replace_siege
from sporebound.player_controller import PlayerController


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk and a display")
class ConfiguredSiegePlayerGuiTests(unittest.TestCase):
    def test_start_from_game_menu_save_and_resume(self):
        import tkinter as tk
        from tkinter import ttk

        def all_children(parent):
            for child in parent.winfo_children():
                yield child
                yield from all_children(child)

        with TemporaryDirectory() as folder:
            path = Path(folder)
            content = Content.load(DEFAULT_CONTENT)
            project = GameProject.load(
                Path(DEFAULT_CONTENT).with_suffix(".game.json"), content)
            # Single-sector plans are also valid, so the UI can launch one
            # without manipulating campaign flags or bypassing mission locks.
            project = replace_siege(
                project, content, new_blueprint("easy_gate", "main", "garden", front="gate"))
            content_path = path / "core.json"
            project_path = path / "core.game.json"
            profile = path / "player.game.json"
            content_path.write_text(json.dumps(content.to_dict()), encoding="utf-8")
            project.save(project_path, content)
            callback_errors = []

            def button(root, title):
                return next(w for w in all_children(root)
                            if isinstance(w, ttk.Button)
                            and w.cget("text") == title)

            def drive_first(root):
                try:
                    root.report_callback_exception = lambda *args: callback_errors.append(args)
                    root.update()
                    button(root, "Nouvelle partie").invoke()
                    root.update()
                    button(root, "Jouer le siège : easy_gate (1 fronts)").invoke()
                    root.update()
                    self.assertTrue(any(isinstance(w, tk.Canvas)
                                        for w in all_children(root)))
                    button(root, "Sauvegarder").invoke()
                    root.update()
                    self.assertEqual(callback_errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive_first), \
                 patch("tkinter.messagebox.showerror") as errors:
                launch(content_path, project_path=project_path, profile_path=profile)
                errors.assert_not_called()
            saved = PlayerController(content, project, profile)
            saved.load_game("main", 1)
            self.assertEqual(saved.session.siege_id, "easy_gate")
            self.assertEqual(saved.session.mode, "fronts")

            def drive_second(root):
                try:
                    root.report_callback_exception = lambda *args: callback_errors.append(args)
                    root.update()
                    button(root, "Continuer").invoke()
                    root.update()
                    button(root, "Timeline / Fronts").invoke()
                    root.update()
                    headings = [w.cget("text") for w in all_children(root)
                                if isinstance(w, ttk.Label)]
                    self.assertIn("Siège : easy_gate", headings)
                    button(root, "Sauvegarder").invoke()
                    self.assertEqual(callback_errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive_second), \
                 patch("tkinter.messagebox.showerror") as errors:
                launch(content_path, project_path=project_path, profile_path=profile)
                errors.assert_not_called()


if __name__ == "__main__":
    unittest.main()
