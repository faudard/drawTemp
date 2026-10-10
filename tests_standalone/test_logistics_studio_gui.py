"""Xvfb visual logistics editor -> saved project -> real Player command UI."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from examples.siege_scenarios import siege_content
from sporebound.editor import launch as launch_editor
from sporebound.player_app import launch as launch_player
from sporebound.game_project import GameProject
from sporebound.model import Content


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a real Tk display")
class LogisticsStudioGuiTests(unittest.TestCase):
    def test_routes_created_in_studio_visible_in_player(self):
        import tkinter as tk
        from tkinter import ttk

        def children(widget):
            for child in widget.winfo_children():
                yield child
                yield from children(child)

        def button(root, text):
            return next(w for w in children(root)
                        if isinstance(w, ttk.Button) and w.cget("text") == text)

        with TemporaryDirectory() as folder:
            path = Path(folder)
            source = path / "siege.json"
            game = path / "siege.game.json"
            profile = path / "player.game.json"
            source.write_text(
                json.dumps(siege_content().to_dict(), ensure_ascii=False),
                encoding="utf-8")
            errors = []

            def drive_editor(root):
                try:
                    root.report_callback_exception = lambda *e: errors.append(e)
                    root.update()
                    self.assertTrue(any(
                        isinstance(w, ttk.Notebook) and
                        "Routes & ressources" in [w.tab(t, "text") for t in w.tabs()]
                        for w in children(root)))
                    button(root, "Nouveau siège").invoke()
                    root.update()
                    button(root, "Activer / enregistrer ressources").invoke()
                    root.update()
                    button(root, "Créer / modifier route").invoke()
                    root.update()
                    button(root, "Enregistrer embuscade").invoke()
                    root.update()
                    button(root, "Aperçu moteur").invoke()
                    root.update()
                    button(root, "Enregistrer projet de jeu…").invoke()
                    root.update()
                    self.assertTrue(game.is_file())
                    self.assertFalse(errors)
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive_editor), \
                 patch("tkinter.simpledialog.askstring", return_value="castle"), \
                 patch("tkinter.filedialog.asksaveasfilename", return_value=str(game)), \
                 patch("tkinter.messagebox.showerror") as message_errors:
                launch_editor(source)
                message_errors.assert_not_called()
            saved = GameProject.load(game, Content.load(source))
            bp = saved.sieges[0]
            self.assertEqual(bp["id"], "castle")
            self.assertEqual(bp["logistics"]["routes"][0]["from"], "reserve")
            self.assertEqual(bp["logistics"]["routes"][0]["to"], "approach")
            self.assertEqual(bp["logistics"]["routes"][0]["turns"], 2)
            self.assertEqual(bp["logistics"]["ambushes"][0]["charges"], 1)

            def drive_player(root):
                try:
                    root.report_callback_exception = lambda *e: errors.append(e)
                    root.update()
                    button(root, "Nouvelle partie").invoke()
                    root.update()
                    button(root, "Jouer le siège : castle (1 fronts)").invoke()
                    root.update()
                    button(root, "Timeline / Fronts").invoke()
                    root.update()
                    self.assertTrue(any(
                        isinstance(w, ttk.LabelFrame) and
                        w.cget("text") == "Routes et ravitaillement"
                        for w in children(root)))
                    self.assertIsNotNone(button(root, "Envoyer réserves"))
                    button(root, "Sauvegarder").invoke()
                    self.assertFalse(errors)
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive_player), \
                 patch("tkinter.messagebox.showerror") as message_errors:
                launch_player(source, project_path=game, profile_path=profile)
                message_errors.assert_not_called()


if __name__ == "__main__":
    unittest.main()
