"""Real Tk 2.5.4.4 Studio route edit -> GameProject -> Player strategic choice."""
import json
import os
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from examples.siege_fronts import SIEGE_CAMPAIGN, siege_session
from examples.siege_scenarios import siege_content
from sporebound.editor import launch as studio_launch
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.player_app import launch as player_launch
from sporebound.player_controller import PlayerController
from sporebound.siege_authoring import replace_siege


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk with virtual display")
class RoutesDiplomacyGuiTests(unittest.TestCase):
    def test_create_tunnel_route_then_play_direct_and_resume(self):
        import tkinter as tk
        from tkinter import ttk

        def children(widget):
            for child in widget.winfo_children():
                yield child
                yield from children(child)

        def button(root, label):
            return next(w for w in children(root)
                        if isinstance(w, ttk.Button) and w.cget("text") == label)

        def field(root, label):
            caption = next(w for w in children(root)
                           if isinstance(w, ttk.Label) and w.cget("text") == label)
            row = caption.grid_info()["row"]
            return next(w for w in caption.master.winfo_children()
                        if isinstance(w, (ttk.Entry, ttk.Combobox))
                        and w.grid_info().get("row") == row
                        and w.grid_info().get("column") == 1)

        with TemporaryDirectory() as folder:
            base = Path(folder)
            content = siege_content()
            s = siege_session(contested=True, campaign=True, paths=True)
            bp = {"id": "castle_routes", "campaign_id": "main",
                  "fronts": deepcopy(s.missions),
                  "focused": "supplies", "specs": deepcopy(s.initial_specs),
                  "links": deepcopy(s.links), "logistics": deepcopy(s.initial_logistics),
                  "campaign": deepcopy(SIEGE_CAMPAIGN)}
            project = replace_siege(
                GameProject(campaigns=[{
                    "id": "main", "name": "Château", "description": "",
                    "start_mission": "castle_supply"}]), content, bp)
            source = base / "castle.json"
            game = base / "castle.game.json"
            profile = base / "player.game.json"
            source.write_text(json.dumps(content.to_dict()), encoding="utf-8")
            project.save(game, content)
            errors = []

            def edit_studio(root):
                try:
                    root.report_callback_exception = lambda *e: errors.append(e)
                    root.update()
                    notebooks = [w for w in children(root) if isinstance(w, ttk.Notebook)]
                    self.assertTrue(any(
                        "Itinéraires & diplomatie" in
                        [w.tab(tab, "text") for tab in w.tabs()] for w in notebooks))
                    button(root, "Activer itinéraires").invoke()
                    root.update()
                    route_id = field(root, "Nom d'itinéraire")
                    route_id.delete(0, "end")
                    route_id.insert(0, "tunnels")
                    field(root, "Front requis (facultatif)").set("tunnels")
                    field(root, "Issues autorisées").delete(0, "end")
                    field(root, "Issues autorisées").insert(0, "victory")
                    button(root, "Enregistrer itinéraire").invoke()
                    root.update()
                    button(root, "Prévisualiser conditions").invoke()
                    button(root, "Enregistrer projet de jeu…").invoke()
                    root.update()
                    self.assertFalse(errors)
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", edit_studio), \
                 patch("tkinter.filedialog.asksaveasfilename",
                       return_value=str(game)), \
                 patch("tkinter.messagebox.showerror") as popup:
                studio_launch(source)
                popup.assert_not_called()
            saved = GameProject.load(game, Content.load(source))
            self.assertIn("tunnels", saved.sieges[0]["campaign"]["routes"])
            self.assertEqual(saved.sieges[0]["campaign"]["routes"]["tunnels"]
                             ["required"], {"tunnels": ["victory"]})

            p = PlayerController(Content.load(source), saved, profile)
            p.new_game("main", 1)
            for mid in saved.sieges[0]["fronts"].values():
                if mid not in p.session.progress.unlocked:
                    p.session.progress.unlocked.append(mid)
            p.save()

            def run_player(root):
                try:
                    root.report_callback_exception = lambda *e: errors.append(e)
                    root.update()
                    button(root, "Continuer").invoke()
                    root.update()
                    button(root, "Jouer le siège : castle_routes (6 fronts)").invoke()
                    root.update()
                    button(root, "Timeline / Fronts").invoke()
                    root.update()
                    self.assertTrue(any(
                        isinstance(w, ttk.LabelFrame) and
                        w.cget("text") == "Routes, accords et reconquête"
                        for w in children(root)))
                    route_caption = next(
                        w for w in children(root)
                        if isinstance(w, ttk.Label) and
                        w.cget("text") == "Approche")
                    route_select = next(
                        w for w in route_caption.master.winfo_children()
                        if isinstance(w, ttk.Combobox))
                    route_select.set("direct")
                    button(root, "Engager itinéraire").invoke()
                    root.update()
                    self.assertFalse(errors)
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", run_player), \
                 patch("tkinter.messagebox.showerror") as popup:
                player_launch(source, project_path=game, profile_path=profile)
                popup.assert_not_called()
            restored = PlayerController(Content.load(source), saved, profile)
            restored.load_game("main", 1)
            self.assertTrue(restored.session.fronts.route_locked)
            self.assertEqual(restored.session.fronts.route_selected, "direct")


if __name__ == "__main__":
    unittest.main()
