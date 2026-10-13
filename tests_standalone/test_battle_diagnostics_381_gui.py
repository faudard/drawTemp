"""Xvfb smoke: seed drilldown launches the real 3.8.1 replay timeline."""
import os
import time
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk display")
class BattleDiagnosticsGUITests(unittest.TestCase):
    def test_selected_seed_opens_replay_without_callback_errors(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        errors = []

        def drive(root):
            try:
                root.report_callback_exception = lambda *err: errors.append(err)
                root.update()
                books = [w for w in descendants(root)
                         if isinstance(w, ttk.Notebook)]
                book = next(w for w in books if
                            "Battle Lab" in [w.tab(tab, "text") for tab in w.tabs()])
                tab = root.nametowidget(next(t for t in book.tabs()
                                             if book.tab(t, "text") == "Battle Lab"))
                book.select(tab)
                widgets = list(descendants(tab))
                entries = [w for w in widgets if isinstance(w, ttk.Entry)]
                for old, value in (("1,7,42,99", "1"), ("500", "8")):
                    field = next(e for e in entries if e.get() == old)
                    field.delete(0, "end")
                    field.insert(0, value)
                buttons = {w.cget("text"): w for w in widgets
                           if isinstance(w, ttk.Button)}
                buttons["Simuler"].invoke()
                rows = next(w for w in widgets if isinstance(w, ttk.Treeview))
                for _ in range(150):
                    root.update()
                    if rows.get_children():
                        break
                    time.sleep(0.02)
                self.assertEqual(len(rows.get_children()), 1)
                rows.selection_set(rows.get_children()[0])
                buttons["Diagnostiquer seed"].invoke()
                for _ in range(150):
                    root.update()
                    windows = [w for w in descendants(root)
                               if isinstance(w, tk.Toplevel)
                               and "Battle Lab · replay" in w.title()]
                    if windows:
                        break
                    time.sleep(0.02)
                self.assertTrue(windows)
                replay = windows[-1]
                trees = [w for w in descendants(replay)
                         if isinstance(w, ttk.Treeview)]
                self.assertTrue(any(len(w.get_children()) >= 2 for w in trees))
                canvas = next(w for w in descendants(replay)
                              if isinstance(w, tk.Canvas))
                self.assertGreater(len(canvas.find_all()), 0)
                self.assertEqual(errors, [])
            finally:
                root.destroy()

        with patch.object(tk.Tk, "mainloop", drive), \
             patch("tkinter.messagebox.showerror") as modal_error:
            launch(DEFAULT_CONTENT)
            modal_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
