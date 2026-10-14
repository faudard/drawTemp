"""Real Tk Matrix scenario construction + background simulation smoke under Xvfb."""
import os
import time
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires active Tk display")
class BalanceMatrixGUITests(unittest.TestCase):
    def test_add_compare_and_inspect_mission(self):
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
                            "Balance Matrix" in [w.tab(tab, "text")
                                                 for tab in w.tabs()])
                tab = root.nametowidget(
                    next(t for t in book.tabs() if
                         book.tab(t, "text") == "Balance Matrix"))
                book.select(tab)
                widgets = list(descendants(tab))
                buttons = {w.cget("text"): w for w in widgets
                           if isinstance(w, ttk.Button)}
                entries = [w for w in widgets if isinstance(w, ttk.Entry)
                           and not isinstance(w, ttk.Combobox)]
                for initial, changed in (("1,7,42,99", "1"),
                                         ("100", "8")):
                    widget = next(w for w in entries if w.get() == initial)
                    widget.delete(0, "end")
                    widget.insert(0, changed)
                buttons["Ajouter scénario"].invoke()
                cases = next(w for w in widgets if isinstance(w, ttk.Treeview))
                self.assertEqual(len(cases.get_children()), 1)
                buttons["Comparer les scénarios"].invoke()
                rows = [w for w in widgets if isinstance(w, ttk.Treeview)][1]
                status = next(w for w in widgets if isinstance(w, ttk.Label)
                              and "Simulations matricielles en cours" in w.cget("text"))
                for _ in range(150):
                    root.update()
                    if status.cget("text").startswith("Terminé"):
                        break
                    time.sleep(0.02)
                self.assertTrue(status.cget("text").startswith("Terminé"))
                self.assertEqual(len(rows.get_children()), 2)
                rows.selection_set(rows.get_children()[-1])
                buttons["Inspecter mission dans Battle Lab"].invoke()
                self.assertEqual(book.tab(book.select(), "text"), "Battle Lab")
                self.assertEqual(errors, [])
            finally:
                root.destroy()

        with patch.object(tk.Tk, "mainloop", drive), \
             patch("tkinter.messagebox.showerror") as dialogs:
            launch(DEFAULT_CONTENT)
            dialogs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
