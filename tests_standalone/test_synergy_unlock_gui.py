"""Tk/Xvfb smoke for secret duo/trio unlock authoring and non-mutating preview."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch
from sporebound.model import Content


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Run with a Tk display or Xvfb")
class SynergyUnlockGUITests(unittest.TestCase):
    def test_create_hidden_combo_edit_condition_preview_and_save(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            saved_file = Path(folder) / "synergy_content.json"
            failures = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *err: failures.append(err)
                    root.update()
                    all_widgets = list(descendants(root))
                    book = next(w for w in all_widgets if isinstance(w, ttk.Notebook)
                                and "Synergies & secrets" in
                                [w.tab(t, "text") for t in w.tabs()])
                    index = next(i for i in range(len(book.tabs()))
                                 if book.tab(i, "text") == "Synergies & secrets")
                    book.select(index)
                    root.update()
                    page = root.nametowidget(book.select())
                    widgets = list(descendants(page))
                    buttons = {w.cget("text"):w for w in widgets
                               if isinstance(w, ttk.Button)}
                    self.assertIn("Nouveau combo", buttons)
                    self.assertIn("Créer / enregistrer", buttons)
                    self.assertTrue(any(isinstance(w, ttk.Treeview)
                                        for w in widgets))
                    buttons["Nouveau combo"].invoke()
                    root.update()
                    tactic = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                  and "crossfire" in tuple(w["values"]))
                    tactic.set("crossfire")
                    members = next(w for w in widgets if type(w) is ttk.Entry
                                   and w.get() == "ziggy,momo")
                    members.delete(0, "end")
                    members.insert(0, "momo,luma")
                    # Tree selection loads the existing "missions_together >= 1".
                    # Set the intended predicate explicitly, as a real author does.
                    stat = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                and "shared_kills" in tuple(w["values"]))
                    stat.set("shared_kills")
                    threshold = next(w for w in widgets if type(w) is ttk.Entry
                                     and w.get() == "1")
                    threshold.delete(0, "end")
                    threshold.insert(0, "2")
                    buttons["Remplacer"].invoke()
                    root.update()
                    buttons["Créer / enregistrer"].invoke()
                    root.update()
                    choices = next(w for w in widgets if isinstance(w, tk.Listbox)
                                   and any("pincer" in w.get(i)
                                           for i in range(w.size())))
                    self.assertTrue(any("crossfire" in choices.get(i)
                                        for i in range(choices.size())))
                    buttons["Simuler découverte"].invoke()
                    root.update()
                    messages = [w.getvar(w.cget("textvariable"))
                                for w in widgets if isinstance(w, ttk.Label)
                                and str(w.cget("textvariable"))]
                    self.assertTrue(any("DÉBLOQUÉ" in str(x) for x in messages),
                                    messages)

                    top_buttons = {w.cget("text"):w for w in descendants(root)
                                   if isinstance(w, ttk.Button)}
                    top_buttons["Enregistrer sous"].invoke()
                    content = Content.load(saved_file)
                    rows = [row for row in content.tactic_unlocks
                            if row["id"] == "crossfire" and
                            set(row["members"]) == {"momo","luma"}]
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]["unlock"],
                                     {"stat":"shared_kills", "gte":2})
                    self.assertEqual(failures, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.filedialog.asksaveasfilename",
                       return_value=str(saved_file)), \
                 patch("tkinter.messagebox.showerror") as show_error:
                launch(DEFAULT_CONTENT)
                show_error.assert_not_called()


if __name__=="__main__":
    unittest.main()
