"""Actual Tk 2.5.4 authoring → play → checkpoint smoke gate.

Run under Xvfb with SPOREBOUND_GUI_SMOKE=1.
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from examples.siege_scenarios import siege_content
from sporebound.editor import launch


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a display")
class CampaignSiegeGUITests(unittest.TestCase):
    def test_create_multifront_without_json_play_save_reload(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            content_file = Path(folder) / "siege.json"
            content_file.write_text(
                json.dumps(siege_content().to_dict(), ensure_ascii=False),
                encoding="utf-8")
            project_file = Path(folder) / "siege.game.json"
            callback_errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: callback_errors.append(exc)
                    root.update()
                    widgets = list(descendants(root))
                    tabs = [w for w in widgets if isinstance(w, ttk.Notebook)]
                    self.assertTrue(any(
                        "Campagne & siège" in [w.tab(t, "text") for t in w.tabs()]
                        for w in tabs))
                    buttons = {w.cget("text"): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    buttons["Nouveau siège"].invoke()
                    root.update()
                    front_label = next(w for w in widgets
                        if isinstance(w, ttk.Label)
                        and w.cget("text") == "Front / identifiant")
                    front_entry = front_label.master.grid_slaves(row=0, column=1)[0]
                    front_entry.delete(0, "end")
                    front_entry.insert(0, "gate")
                    buttons["+ Front"].invoke()
                    root.update()
                    buttons["Simuler 8 tours"].invoke()
                    buttons["Démarrer / rejouer"].invoke()
                    root.update()
                    buttons["Enregistrer projet de jeu…"].invoke()
                    root.update()
                    buttons["Sauver partie"].invoke()
                    root.update()
                    saved = Path(folder) / "siege.game_saves" / "siege_castle" / "slot_1.json"
                    self.assertTrue(saved.is_file())
                    buttons["Charger siège"].invoke()
                    root.update()
                    authored = json.loads(project_file.read_text(encoding="utf-8"))
                    self.assertEqual(len(authored["sieges"]), 1)
                    self.assertEqual(len(authored["sieges"][0]["fronts"]), 2)
                    self.assertEqual(callback_errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.simpledialog.askstring", return_value="castle"), \
                 patch("tkinter.filedialog.asksaveasfilename",
                       return_value=str(project_file)), \
                 patch("tkinter.messagebox.showerror") as errors:
                launch(content_file)
                errors.assert_not_called()


if __name__ == "__main__":
    unittest.main()
