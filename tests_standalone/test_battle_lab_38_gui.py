"""Real Tk 3.8 Battle Lab smoke, run under Xvfb."""
import os
import time
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires an active Tk display")
class BattleLabGUITests(unittest.TestCase):
    def test_lab_opens_and_completes_one_headless_run(self):
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
                notebooks = [w for w in descendants(root)
                             if isinstance(w, ttk.Notebook)]
                book = next(w for w in notebooks if
                            "Battle Lab" in [w.tab(tab, "text") for tab in w.tabs()])
                tab_id = next(tab for tab in book.tabs()
                              if book.tab(tab, "text") == "Battle Lab")
                tab = root.nametowidget(tab_id)
                book.select(tab)
                widgets = list(descendants(tab))
                entries = [w for w in widgets if isinstance(w, ttk.Entry)]
                seed_entry = next(w for w in entries
                                  if w.get() == "1,7,42,99")
                cap_entry = next(w for w in entries if w.get() == "500")
                for entry, value in ((seed_entry, "1"), (cap_entry, "8")):
                    entry.delete(0, "end")
                    entry.insert(0, value)
                go = next(w for w in widgets if isinstance(w, ttk.Button)
                          and w.cget("text") == "Simuler")
                go.invoke()
                status = next(w for w in widgets if isinstance(w, ttk.Label)
                              and "Simulation en cours" in w.cget("text"))
                for _ in range(150):
                    root.update()
                    if status.cget("text").startswith("Terminé"):
                        break
                    time.sleep(0.02)
                self.assertTrue(status.cget("text").startswith("Terminé"))
                rows = next(w for w in widgets if isinstance(w, ttk.Treeview))
                self.assertEqual(len(rows.get_children()), 1)
                self.assertEqual(errors, [])
            finally:
                root.destroy()

        with patch.object(tk.Tk, "mainloop", drive), \
             patch("tkinter.messagebox.showerror") as dialogs:
            launch(DEFAULT_CONTENT)
            dialogs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
