"""3.8.3 GUI smoke: actual Studio sweep → canvas → verified CT → replay."""
import os
import time
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a live Tk display / Xvfb")
class VisualBattleLabGUITests(unittest.TestCase):
    def test_visual_drilldown_and_replay_without_engine_edits(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        errors = []

        def drive(root):
            try:
                root.report_callback_exception = lambda *exc: errors.append(exc)
                root.update()
                books = [w for w in descendants(root)
                         if isinstance(w, ttk.Notebook)]
                book = next(w for w in books if
                            {"Battle Lab", "Balance Matrix", "Visual Battle Lab"}
                            <= {w.tab(x, "text") for x in w.tabs()})
                tab = {book.tab(t, "text"): root.nametowidget(t)
                       for t in book.tabs()}
                book.select(tab["Battle Lab"])
                battle_widgets = list(descendants(tab["Battle Lab"]))
                entries = [w for w in battle_widgets if isinstance(w, ttk.Entry)
                           and not isinstance(w, ttk.Combobox)]
                for old, new in (("1,7,42,99", "1"), ("500", "9")):
                    entry = next(w for w in entries if w.get() == old)
                    entry.delete(0, "end")
                    entry.insert(0, new)
                battle_buttons = {w.cget("text"): w for w in battle_widgets
                                  if isinstance(w, ttk.Button)}
                battle_buttons["Simuler"].invoke()
                status = next(w for w in battle_widgets
                              if isinstance(w, ttk.Label)
                              and "Simulation en cours" in w.cget("text"))
                for _ in range(150):
                    root.update()
                    if status.cget("text").startswith("Terminé"):
                        break
                    time.sleep(0.02)
                self.assertTrue(status.cget("text").startswith("Terminé"))
                battle_rows = next(w for w in battle_widgets
                                   if isinstance(w, ttk.Treeview))
                self.assertEqual(len(battle_rows.get_children()), 1)
                battle_rows.selection_set(battle_rows.get_children()[0])
                battle_buttons["Visualiser résultats"].invoke()
                root.update()
                self.assertEqual(book.tab(book.select(), "text"),
                                 "Visual Battle Lab")
                widgets = list(descendants(tab["Visual Battle Lab"]))
                canvases = [w for w in widgets if isinstance(w, tk.Canvas)]
                self.assertEqual(len(canvases), 4)
                self.assertTrue(all(c.find_all() for c in canvases[:3]))
                rows = next(w for w in widgets if isinstance(w, ttk.Treeview))
                self.assertEqual(len(rows.get_children()), 1)
                buttons = {w.cget("text"): w for w in widgets
                           if isinstance(w, ttk.Button)}
                buttons["Tracer seed sélectionnée"].invoke()
                status = next(w for w in widgets if isinstance(w, ttk.Label)
                              and "Rejoue et vérifie" in w.cget("text"))
                for _ in range(150):
                    root.update()
                    if "replay vérifié" in status.cget("text"):
                        break
                    time.sleep(0.02)
                self.assertIn("replay vérifié", status.cget("text"))
                self.assertTrue(canvases[3].find_all())
                buttons["Replay détaillé"].invoke()
                root.update()
                viewers = [w for w in descendants(root) if
                           isinstance(w, tk.Toplevel) and
                           "Battle Lab · replay" in w.title()]
                self.assertTrue(viewers)
                self.assertFalse(errors)
            finally:
                root.destroy()

        with patch.object(tk.Tk, "mainloop", drive), \
             patch("tkinter.messagebox.showerror") as dialogs:
            launch(DEFAULT_CONTENT)
            dialogs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
