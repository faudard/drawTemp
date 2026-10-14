"""R5.14 real Tk branch exploration: no content, project or save modifications."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from examples.reliability_gate import fixture
from sporebound.editor import launch


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Xvfb / Tk")
class CampaignSimulationGUITests(unittest.TestCase):
    def test_branch_from_parent_compare_and_leave_project_untouched(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        content, project = fixture()
        project.campaign_flow = {
            "endings": {
                "mercy": {"flag": "ending", "eq": "mercy"},
                "occupation": {"flag": "ending", "eq": "occupation"},
            },
        }
        project.validate(content)
        with TemporaryDirectory() as dirname:
            root_path = Path(dirname)
            path = root_path / "story.json"
            game_path = root_path / "story.game.json"
            path.write_text(json.dumps(content.to_dict()), encoding="utf-8")
            project.save(game_path, content)
            content_before, project_before = path.read_bytes(), game_path.read_bytes()
            callback_errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *args: callback_errors.append(args)
                    root.update()
                    books = [w for w in descendants(root) if isinstance(w, ttk.Notebook)]
                    book = next(w for w in books
                                if "Campaign Simulation" in
                                [w.tab(t, "text") for t in w.tabs()])
                    tab = next(t for t in book.tabs()
                               if book.tab(t, "text") == "Campaign Simulation")
                    book.select(tab)
                    root.update()
                    page = root.nametowidget(book.select())
                    widgets = list(descendants(page))
                    buttons = {w.cget("text"): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    tree = next(w for w in widgets if isinstance(w, ttk.Treeview))
                    actions = next(w for w in widgets if isinstance(w, tk.Listbox))
                    buttons["Nouvelle simulation"].invoke()
                    root.update()
                    self.assertEqual(len(tree.get_children()), 1)
                    self.assertIn("Dialogue", actions.get(0))
                    actions.selection_set(0)
                    buttons["Exécuter l'action"].invoke()
                    root.update()
                    self.assertIn("Victoire supposée", actions.get(0))
                    self.assertEqual(len(tree.get_children("n0")), 1)
                    buttons["Comparer A"].invoke()
                    root.update()
                    actions.selection_set(0)
                    buttons["Exécuter l'action"].invoke()
                    root.update()
                    buttons["Comparer B"].invoke()
                    root.update()
                    buttons["Revenir au parent"].invoke()
                    root.update()
                    buttons["Créer une bifurcation"].invoke()
                    root.update()
                    self.assertGreaterEqual(len(tree.get_children("n1")), 2)
                    self.assertTrue(root.winfo_exists())
                    self.assertEqual(callback_errors, [])
                    self.assertEqual(path.read_bytes(), content_before)
                    self.assertEqual(game_path.read_bytes(), project_before)
                    self.assertEqual(list(root_path.rglob("*.json")),
                                     [path, game_path])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.messagebox.showerror") as errors:
                launch(path)
                errors.assert_not_called()


if __name__ == "__main__":
    unittest.main()
