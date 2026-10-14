"""R6.15 Studio smoke: real Matrix selection, quality worker and human pending."""
import json
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk and a virtual display")
class TacticalQualityStudioTests(unittest.TestCase):
    def test_quality_analysis_does_not_fake_human_signoff(self):
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
                            "Balance Matrix" in
                            [w.tab(t, "text") for t in w.tabs()])
                tab = root.nametowidget(next(
                    t for t in book.tabs()
                    if book.tab(t, "text") == "Balance Matrix"))
                book.select(tab)
                widgets = list(descendants(tab))
                buttons = {w.cget("text"): w for w in widgets
                           if isinstance(w, ttk.Button)}
                self.assertIn("R6.15 · Mesurer les compromis", buttons)
                self.assertIn("Revue humaine R6.15", buttons)
                entries = [w for w in widgets
                           if isinstance(w, ttk.Entry)
                           and not isinstance(w, ttk.Combobox)]
                for initial, changed in (("1,7,42,99", "1"),
                                         ("100", "8")):
                    entry = next(w for w in entries if w.get() == initial)
                    entry.delete(0, "end")
                    entry.insert(0, changed)
                status = next(
                    w for w in widgets if isinstance(w, ttk.Label) and
                    w.cget("text").startswith("Prêt · aucun scénario"))
                buttons["Ajouter scénario"].invoke()
                buttons["Comparer les scénarios"].invoke()
                for _ in range(350):
                    root.update()
                    if status.cget("text").startswith("Terminé"):
                        break
                    time.sleep(.02)
                self.assertTrue(status.cget("text").startswith("Terminé"),
                                status.cget("text"))
                tables = [w for w in widgets if isinstance(w, ttk.Treeview)]
                table = tables[1]
                self.assertEqual(len(table.get_children()), 2)
                table.selection_set(table.get_children()[-1])
                buttons["R6.15 · Mesurer les compromis"].invoke()
                for _ in range(350):
                    root.update()
                    if "mesures prêtes" in status.cget("text"):
                        break
                    time.sleep(.02)
                self.assertIn("mesures prêtes", status.cget("text"))
                detail = next(w for w in widgets if isinstance(w, tk.Text))
                self.assertIn("EN ATTENTE de playtests",
                              detail.get("1.0", "end"))

                # Synthetic sessions cannot satisfy release without consent,
                # compatible authored content, and explicit human checkboxes.
                with TemporaryDirectory() as tmp:
                    human = Path(tmp) / "human.json"
                    human.write_text(json.dumps({
                        "kind": "human_playtest", "schema": 1, "opt_in": True,
                        "sessions": [{
                            "mission": "garden", "outcome": "victory",
                            "duration_seconds": 1200, "partial_capture": False,
                            "truncated_events": 0, "events": [],
                            "command_kinds": {"act": 1},
                            "damage_observed": 0, "healing_observed": 0,
                            "objective_hold_ticks": 0,
                            "goal_occupied": False}
                            for _ in range(5)]}), encoding="utf-8")
                    with patch("tkinter.filedialog.askopenfilename",
                               side_effect=[str(human), ""]):
                        buttons["Revue humaine R6.15"].invoke()
                    root.update()
                    modal = next((w for w in root.winfo_children()
                                  if isinstance(w, tk.Toplevel)), None)
                    self.assertIsNotNone(modal)
                    checkboxes = [w for w in descendants(modal)
                                  if isinstance(w, ttk.Checkbutton)]
                    self.assertEqual(len(checkboxes), 5)
                    approve = next(w for w in descendants(modal)
                                   if isinstance(w, ttk.Button)
                                   and w.cget("text") == "Évaluer la revue")
                    approve.invoke()
                    root.update()
                    self.assertIn("PENDING", status.cget("text"))
                self.assertEqual(errors, [])
            finally:
                root.destroy()

        with patch.object(tk.Tk, "mainloop", drive), \
             patch("tkinter.messagebox.showerror") as dialogs:
            launch(DEFAULT_CONTENT)
            dialogs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
