"""GUI smoke: create, edit and preview a siege without editing JSON."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch
from sporebound.game_project import GameProject
from sporebound.model import Content


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk/Xvfb display")
class SiegeStudioGUITests(unittest.TestCase):
    def test_visual_fronts_routes_preview_and_project_roundtrip(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            path = Path(folder) / "siege.game.json"
            exceptions = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: exceptions.append(exc)
                    root.update()
                    all_widgets = list(descendants(root))
                    tabs = next(widget for widget in all_widgets
                                if isinstance(widget, ttk.Notebook)
                                and "Campagne & sièges" in
                                [widget.tab(tab, "text") for tab in widget.tabs()])
                    tab = next(i for i in range(len(tabs.tabs()))
                               if tabs.tab(i, "text") == "Campagne & sièges")
                    tabs.select(tab)
                    root.update()
                    page = root.nametowidget(tabs.select())
                    widgets = list(descendants(page))
                    buttons = {w.cget("text"): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    self.assertIn("Créer siège", buttons)
                    self.assertIn("Simuler 5 tours", buttons)
                    buttons["Créer siège"].invoke()
                    root.update()
                    fronts = next(w for w in widgets
                                  if isinstance(w, tk.Listbox))
                    self.assertEqual(fronts.size(), 2)
                    buttons["Simuler 5 tours"].invoke()
                    root.update()
                    preview = next(w for w in widgets if isinstance(w, tk.Text))
                    self.assertIn("Tour 5", preview.get("1.0", "end"))
                    buttons["Annuler siège"].invoke()
                    root.update()
                    self.assertEqual(fronts.size(), 0)
                    buttons["Rétablir siège"].invoke()
                    root.update()
                    self.assertEqual(fronts.size(), 2)
                    overall = {w.cget("text"): w for w in descendants(root)
                               if isinstance(w, ttk.Button)}
                    overall["Enregistrer projet de jeu…"].invoke()
                    data = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(len(data["sieges"]["main"]["missions"]), 2)
                    GameProject.from_dict(data, Content.load(DEFAULT_CONTENT))
                    self.assertEqual(exceptions, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.filedialog.asksaveasfilename",
                       return_value=str(path)), \
                 patch("tkinter.messagebox.showerror") as show_error:
                launch(DEFAULT_CONTENT)
                show_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
