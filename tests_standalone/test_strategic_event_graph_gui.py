"""Xvfb: create strategic node without JSON, persist and launch same battle."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from examples.siege_scenarios import siege_content
from sporebound.editor import launch
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.siege_authoring import make_session


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk / Xvfb")
class StrategicEventGraphGUITests(unittest.TestCase):
    def test_author_event_from_studio_and_replay(self):
        import tkinter as tk
        from tkinter import ttk

        def all_children(widget):
            for child in widget.winfo_children():
                yield child
                yield from all_children(child)

        def click(root, title):
            return next(w for w in all_children(root)
                        if isinstance(w, ttk.Button) and w.cget("text") == title)

        with TemporaryDirectory() as folder:
            content_path = Path(folder) / "castle.json"
            project_path = Path(folder) / "castle.game.json"
            content_path.write_text(
                json.dumps(siege_content().to_dict(), ensure_ascii=False),
                encoding="utf-8")
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *e: errors.append(e)
                    root.update()
                    self.assertTrue(any(
                        isinstance(w, ttk.Notebook) and
                        "Graphe stratégique" in [w.tab(tab, "text") for tab in w.tabs()]
                        for w in all_children(root)))
                    click(root, "Nouveau siège").invoke()
                    root.update()
                    click(root, "Nouveau").invoke()
                    root.update()
                    click(root, "Envelopper").invoke()
                    root.update()
                    # AND of the same turn predicate remains valid.
                    click(root, "+ Dans ET/OU").invoke()
                    root.update()
                    click(root, "Simuler 8 tours").invoke()
                    root.update()
                    click(root, "Enregistrer projet de jeu…").invoke()
                    root.update()
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.simpledialog.askstring", return_value="castle"), \
                 patch("tkinter.filedialog.asksaveasfilename",
                       return_value=str(project_path)), \
                 patch("tkinter.messagebox.showerror") as popup:
                launch(content_path)
                popup.assert_not_called()
            project = GameProject.load(project_path, Content.load(content_path))
            bp = project.sieges[0]
            self.assertEqual(len(bp["event_graph"]), 1)
            self.assertEqual(bp["event_graph"][0]["when"], {
                "all": [{"turn_at_least": 3}, {"turn_at_least": 3}]})
            session = make_session(bp, Content.load(content_path))
            for _ in range(3):
                session.advance()
            self.assertEqual(session.fired_graph, {"reinforcements_delayed"})
            self.assertEqual(type(session).replay(session.recording()).digest(),
                             session.digest())


if __name__ == "__main__":
    unittest.main()
