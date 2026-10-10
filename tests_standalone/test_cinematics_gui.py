"""Real Tk smoke: author a cinematic, preview, skip and save without editing JSON."""
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
                     "Requires Tk and a display")
class CinematicGUITests(unittest.TestCase):
    def test_studio_creates_previews_and_saves_cinematic(self):
        import tkinter as tk
        from tkinter import ttk

        def all_widgets(widget):
            for child in widget.winfo_children():
                yield child
                yield from all_widgets(child)

        with TemporaryDirectory() as folder:
            content_file = Path(folder) / "mission.json"
            content_file.write_text(Path(DEFAULT_CONTENT).read_text(encoding="utf-8"),
                                    encoding="utf-8")
            project_file = Path(folder) / "mission.game.json"
            callback_errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *err: callback_errors.append(err)
                    root.update()
                    widgets = list(all_widgets(root))
                    notebooks = [w for w in widgets if isinstance(w, ttk.Notebook)]
                    self.assertTrue(any("Cinématiques" in [
                        w.tab(tab, "text") for tab in w.tabs()] for w in notebooks))
                    buttons = {w.cget("text"): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    buttons["Exemple Jeanne"].invoke()
                    root.update()
                    self.assertEqual(showerror.call_args_list, [],
                                     "Studio rejected sample cinematic")
                    widgets = list(all_widgets(root))
                    self.assertTrue(any(
                        isinstance(w, tk.Listbox) and
                        any("jeanne_prologue" in w.get(i)
                            for i in range(w.size()))
                        for w in widgets), "Sample cinematic missing from Studio list")
                    buttons["Bande-son Jeanne"].invoke()
                    root.update()
                    self.assertEqual(showerror.call_args_list, [],
                                     "Jeanne audio tracks rejected")
                    buttons["Lecture complète"].invoke()
                    root.update()
                    self.assertEqual(showerror.call_args_list, [],
                                     "Cinematic preview was rejected")
                    # Toplevel is parented to the Studio tab, not the Tk root.
                    self.assertTrue(any(isinstance(w, tk.Toplevel)
                                        for w in all_widgets(root)))
                    skip = next(w for w in all_widgets(root)
                                if isinstance(w, ttk.Button)
                                and w.cget("text") == "Passer la cinématique")
                    skip.invoke()
                    root.update()
                    buttons["Enregistrer projet"].invoke()
                    root.update()
                    project = GameProject.load(project_file, Content.load(content_file))
                    self.assertEqual(project.cinematics[0]["id"], "jeanne_prologue")
                    self.assertEqual(len(project.cinematics[0]["events"]), 9)
                    self.assertEqual(
                        {e["bus"] for e in project.cinematics[0]["events"]
                         if e["kind"] == "sound"},
                        {"music", "ambience", "voice"})
                    self.assertEqual(callback_errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.filedialog.asksaveasfilename",
                       return_value=str(project_file)), \
                 patch("tkinter.messagebox.showerror") as showerror:
                launch(content_file)
                showerror.assert_not_called()


if __name__ == "__main__":
    unittest.main()
