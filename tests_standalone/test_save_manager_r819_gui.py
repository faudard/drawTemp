"""R8.19 Player Save Manager real-Tk navigation smoke (opt-in Xvfb)."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.player_controller import PlayerController
from sporebound.save_maintenance import LongSessionMaintenance
from sporebound.player_app import launch


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires an actual Tk display (xvfb-run)")
class SaveManagerGuiTests(unittest.TestCase):
    def test_title_entry_history_compare_and_cancel_without_side_effects(self):
        import tkinter as tk
        from tkinter import ttk

        def children(root):
            for widget in root.winfo_children():
                yield widget
                yield from children(widget)

        with TemporaryDirectory() as folder:
            profile = Path(folder) / "smoke.game.json"
            content = Content.load(DEFAULT_CONTENT)
            project = GameProject.load(
                Path(DEFAULT_CONTENT).with_suffix(".game.json"), content)
            player = PlayerController(content, project, profile)
            player.new_long_game("main", 1, seed=17)
            manager = LongSessionMaintenance(
                player.long_path_for("main", 1), content, project,
                rules=player.rules)
            archived = manager.archive_verified()
            checkpoint = player.long_path_for("main", 1)
            previous = (checkpoint.read_bytes(),
                        Path(str(checkpoint) + ".journal").read_bytes())
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *args: errors.append(args)
                    root.update()

                    def button(label):
                        return next(w for w in children(root)
                                    if isinstance(w, ttk.Button) and
                                    w.cget("text") == label)

                    button("Gestionnaire de sauvegardes").invoke()
                    root.update()
                    trees = [w for w in children(root)
                             if isinstance(w, ttk.Treeview)]
                    self.assertEqual(len(trees), 2)
                    explorer, versions = trees
                    self.assertTrue(explorer.exists("1:long"))
                    explorer.selection_set("1:long")
                    explorer.focus("1:long")
                    explorer.event_generate("<<TreeviewSelect>>")
                    root.update()
                    self.assertTrue(versions.exists(archived["name"]))
                    versions.focus(archived["name"])
                    versions.selection_set(archived["name"])
                    button("Comparer").invoke()
                    root.update()
                    report = next(w for w in children(root) if isinstance(w, tk.Text))
                    self.assertIn("Comparaison", report.get("1.0", "end"))
                    button("Retour").invoke()
                    root.update()
                    self.assertTrue(any(w.cget("text") == "Gestionnaire de sauvegardes"
                                        for w in children(root)
                                        if isinstance(w, ttk.Button)))
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.messagebox.showerror") as error_box:
                launch(DEFAULT_CONTENT, profile_path=profile)
                error_box.assert_not_called()
            self.assertEqual(previous[0], checkpoint.read_bytes())
            self.assertEqual(previous[1], Path(str(checkpoint) +
                                               ".journal").read_bytes())


if __name__ == "__main__":
    unittest.main()
