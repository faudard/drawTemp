"""2.8.2 smoke: Studio-authored map and story open in graphical Player."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from examples.siege_scenarios import siege_content
from sporebound.game_project import GameProject
from sporebound import siege_authoring as edit
from sporebound.studio_siege_player_app import launch
from sporebound.authored_siege_player import AuthoredSiegeController


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk/Xvfb")
class AuthoredSiegePlayerGuiTests(unittest.TestCase):
    def test_custom_studio_blueprint_story_tactics_strategy_and_resume(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(root):
            for widget in root.winfo_children():
                yield widget
                yield from descendants(widget)

        content = siege_content()
        bp = edit.new_blueprint("my_siege", "main", "castle_ram", front="gate")
        bp = edit.add_front(bp, "walls", "castle_ramparts")
        project = edit.replace_siege(GameProject.default(content), content, bp)
        project.story = {
            "scenes": [{"id": "intro", "title": "Avant l'assaut",
                        "speaker": "La commandante", "text": "Préparez l'assaut.",
                        "choices": [{"id": "continue", "label": "À l'attaque"}]}],
            "entry_scenes": {"main": "intro"},
            "after_mission": {},
        }
        project.validate(content)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "castle.game.json"
            callbacks = []

            def drive(root):
                root.report_callback_exception = lambda *args: callbacks.append(args)
                try:
                    root.update()
                    def button(name):
                        return next(w for w in descendants(root)
                                    if isinstance(w, ttk.Button)
                                    and w.cget("text") == name)
                    button("Nouvelle partie").invoke()
                    root.update()
                    self.assertTrue(any(
                        isinstance(w, ttk.LabelFrame)
                        and w.cget("text") == "La commandante"
                        for w in descendants(root)))
                    button("À l\u0027attaque").invoke()
                    root.update()
                    self.assertTrue(any(isinstance(w, ttk.Treeview)
                                        for w in descendants(root)))
                    button("Jouer sur la carte").invoke()
                    root.update()
                    self.assertTrue(any(isinstance(w, tk.Canvas)
                                        for w in descendants(root)))
                    button("Début du combat").invoke()
                    root.update()
                    button("Carte des fronts / Diplomatie").invoke()
                    root.update()
                    button("Sauvegarder").invoke()
                    root.update()
                    self.assertEqual(callbacks, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.messagebox.showerror") as errors:
                launch(content, bp, project, path)
                errors.assert_not_called()
            saved = AuthoredSiegeController(content, bp, path)
            saved.continue_game()
            self.assertFalse(saved.session.fronts.active.deploying)
            self.assertIn("execute", [c["kind"] for c in saved.session.fronts.history])


if __name__ == "__main__":
    unittest.main()
