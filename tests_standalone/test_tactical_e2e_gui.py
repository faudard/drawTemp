"""Studio -> content file -> campaign JP -> Player GUI -> combat integration.

The *real* Tk controls are driven under Xvfb. This does not mock the engine,
content validation, campaign slots, or the GUI navigation callbacks.
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.model import Board, Content, Mission, Unit
from sporebound.game_project import GameProject
from sporebound.player_session import PlayerSession
from sporebound.editor import launch as studio_launch
from sporebound.player_shell import launch as player_launch


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk and a graphical display")
class TacticalEndToEndGUITests(unittest.TestCase):
    def test_talent_from_studio_form_to_player_purchase_and_real_battle(self):
        import tkinter as tk
        from tkinter import ttk

        def children(parent):
            for child in parent.winfo_children():
                yield child
                yield from children(child)

        def buttons(root):
            return {w.cget("text"): w for w in children(root)
                    if isinstance(w, ttk.Button)}

        def form_field(root, label):
            for w in children(root):
                if isinstance(w, ttk.Label) and w.cget("text") == label:
                    row = w.grid_info()["row"]
                    return next(s for s in w.master.winfo_children()
                                if isinstance(s, (ttk.Entry, ttk.Combobox))
                                and s.grid_info().get("row") == row
                                and s.grid_info().get("column") == 1)
            raise AssertionError(f"No field for {label}")

        def fill(root, label, value):
            widget = form_field(root, label)
            if isinstance(widget, ttk.Combobox):
                widget.set(value)
            else:
                widget.delete(0, "end")
                widget.insert(0, value)

        with TemporaryDirectory() as folder:
            base = Path(folder)
            original = base / "original.json"
            saved = base / "authored.json"
            profile = base / "player.game.json"
            content = Content({}, {"arena": Mission(
                "arena", "Arena", Board(7, 5),
                [Unit("hero", "Hero", "player", (1, 1)),
                 Unit("enemy", "Enemy", "enemy", (4, 1))])},
                jobs={"brave": {}})
            original.write_text(json.dumps(content.to_dict()), encoding="utf-8")
            gui_errors = []

            def drive_studio(root):
                try:
                    root.report_callback_exception = (
                        lambda *error: gui_errors.append(error))
                    root.update()
                    fill(root, "Talent ID", "shield_training")
                    fill(root, "Coût JP", "2")
                    fill(root, "Stat modifiée", "defense")
                    fill(root, "Bonus", "3")
                    buttons(root)["Créer / mettre à jour"].invoke()
                    root.update()
                    tree = next(w for w in children(root)
                                if isinstance(w, ttk.Treeview)
                                and w.exists("shield_training"))
                    self.assertTrue(tree.exists("shield_training"))
                    buttons(root)["Enregistrer sous"].invoke()
                    self.assertTrue(saved.exists())
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive_studio), \\
                 patch("tkinter.filedialog.asksaveasfilename",
                       return_value=str(saved)), \\
                 patch("tkinter.messagebox.showerror") as studio_errors:
                studio_launch(original)
                studio_errors.assert_not_called()
            self.assertEqual(gui_errors, [])

            authored = Content.load(saved)
            self.assertEqual(
                authored.jobs["brave"]["talents"]["shield_training"]["bonuses"],
                {"defense": 3})
            project = GameProject.default(authored)
            session = PlayerSession(authored, project, profile)
            session.new_game("main", 1)
            session.progress.hero("hero").job_xp["brave"] = 150
            session.save()

            def drive_player(root):
                try:
                    root.report_callback_exception = (
                        lambda *error: gui_errors.append(error))
                    root.update()
                    buttons(root)["Continuer / charger"].invoke()
                    root.update()
                    buttons(root)["Talents / classes"].invoke()
                    root.update()
                    tree = next(w for w in children(root)
                                if isinstance(w, ttk.Treeview)
                                and w.exists("shield_training"))
                    tree.selection_set("shield_training")
                    buttons(root)["Apprendre le talent"].invoke()
                    root.update()
                    purchased = next(w for w in children(root)
                                     if isinstance(w, ttk.Treeview)
                                     and w.exists("shield_training"))
                    self.assertIn("Acquis", purchased.item(
                        "shield_training", "text"))
                    buttons(root)["Retour à la campagne"].invoke()
                    root.update()
                    next(w for title, w in buttons(root).items()
                         if "Arena" in title and "eliminate" in title).invoke()
                    root.update()
                    self.assertIn("Abandonner et revenir à la campagne",
                                  buttons(root))
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive_player), \\
                 patch("tkinter.messagebox.showerror") as player_errors:
                player_launch(saved, profile_path=profile)
                player_errors.assert_not_called()
            self.assertEqual(gui_errors, [])

            resumed = PlayerSession(authored, project, profile)
            resumed.load_game("main", 1)
            self.assertEqual(
                resumed.progress.hero("hero").learned_talents["brave"],
                ["shield_training"])
            self.assertEqual(resumed.progress.hero("hero").spent_jp["brave"], 2)
            battle = resumed.begin("arena")
            self.assertEqual(battle.unit("hero").defense, 3)


if __name__ == "__main__":
    unittest.main()
