"""Real Tk smoke for Jeanne Chapter I, using the actual Player and saved slot."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.player_app import launch


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk and a display (e.g. Xvfb)")
class JeanneChapterDemoGuiTests(unittest.TestCase):
    def test_title_recruitment_briefing_and_first_iso_battle(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            profile = Path(folder) / "jeanne_chapter1.game.json"
            from sporebound.__main__ import DEFAULT_GAME_CONTENT
            project = DEFAULT_GAME_CONTENT.with_suffix(".game.json")
            exceptions = []

            def drive(root):
                root.report_callback_exception = lambda *args: exceptions.append(args)
                try:
                    root.geometry("800x580")
                    root.update()

                    def button(prefix):
                        return next(
                            w for w in descendants(root)
                            if isinstance(w, ttk.Button)
                            and w.cget("text").startswith(prefix))

                    button("Commencer le chapitre I").invoke()
                    root.update()
                    self.assertTrue(any(
                        isinstance(w, ttk.LabelFrame)
                        and w.cget("text") == "Acte I — Le camp des réfugiés"
                        for w in descendants(root)))
                    button("Recruter Étienne").invoke()
                    root.update()
                    button("Étape 01").invoke()
                    root.update()
                    self.assertTrue(any(
                        isinstance(w, ttk.Label)
                        and w.cget("text") == "VOTRE OBJECTIF"
                        for w in descendants(root)))
                    entry = button("Entrer en mission")
                    self.assertGreater(entry.winfo_width(), 0)
                    self.assertLessEqual(
                        entry.winfo_rooty() + entry.winfo_height(),
                        root.winfo_rooty() + root.winfo_height())
                    entry.invoke()
                    root.update()

                    self.assertTrue(any(isinstance(w, tk.Canvas)
                                        for w in descendants(root)))
                    projection = next(
                        w for w in descendants(root)
                        if isinstance(w, ttk.Checkbutton)
                        and w.cget("text") == "Vue 2.5D")
                    self.assertTrue(bool(int(
                        projection.getvar(projection.cget("variable")))))
                    self.assertTrue(any(
                        isinstance(w, ttk.Label) and
                        "Atteindre les cases de sortie" in w.cget("text")
                        for w in descendants(root)))
                    self.assertFalse(exceptions)
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.messagebox.showerror") as errors:
                launch(DEFAULT_GAME_CONTENT, project, profile, chapter_one=True)
                errors.assert_not_called()


if __name__ == "__main__":
    unittest.main()
