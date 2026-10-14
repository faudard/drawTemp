"""R5.13 actual Tk authoring flow: condition + consequence, undo/redo, save."""
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
                     "Requires a display or Xvfb")
class CampaignFlowEditorGUITests(unittest.TestCase):
    def test_visual_authoring_undo_redo_save_and_runtime_gate(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            project_file = Path(folder) / "campaign.game.json"
            callback_errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: callback_errors.append(exc)
                    root.update()
                    widgets = list(descendants(root))
                    book = next(
                        w for w in widgets if isinstance(w, ttk.Notebook)
                        and "Campaign Flow 3.0" in [w.tab(t, "text") for t in w.tabs()])
                    tab = next(tab for tab in book.tabs()
                               if book.tab(tab, "text") == "Campaign Flow 3.0")
                    book.select(tab)
                    root.update()
                    page = root.nametowidget(book.select())
                    elements = list(descendants(page))
                    buttons = {w.cget("text"): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    editor_buttons = {w.cget("text"): w for w in elements
                                      if isinstance(w, ttk.Button)}
                    combos = [w for w in elements if isinstance(w, ttk.Combobox)]
                    target = next(w for w in combos
                                  if "ending" in tuple(w["values"]))
                    target.set("gate")
                    target_name = next(w for w in combos
                                       if w is not target and
                                       "hold" in tuple(w["values"]))
                    target_name.set("hold")
                    editor_buttons["Voir condition"].invoke()
                    preset = next(w for w in combos
                                  if "Mission terminée" in tuple(w["values"]))
                    preset.set("Mission terminée")
                    # The key is a dedicated editable combobox controlled by the
                    # condition form, not raw JSON.
                    entries = [w for w in combos if not w.cget("state") == "readonly"]
                    key = next(w for w in entries if w is not target_name
                               and w is not target
                               and w.get() == "reputation_village")
                    key.set("garden")
                    editor_buttons["Créer / remplacer"].invoke()
                    root.update()
                    tree = next(w for w in elements if isinstance(w, ttk.Treeview))
                    self.assertEqual(len(tree.get_children()), 1)
                    first = tree.item(tree.get_children()[0], "text")
                    self.assertTrue(first)
                    # Set a cross-mission consequence from the same Studio tab.
                    effect_kind = next(w for w in combos
                                       if "heal_wound" in tuple(w["values"]))
                    effect_kind.set("set_flag")
                    effect_kind.event_generate("<<ComboboxSelected>>")
                    root.update()
                    # Textvariables are model-owned; locate them from the UI's
                    # initial/default values instead of window position.
                    editables = [w for w in combos
                                 if w not in (target, target_name, key)
                                 and w.cget("state") != "readonly"]
                    self.assertGreaterEqual(len(editables), 2)
                    form_a = editables[-2]
                    form_b = editables[-1]
                    form_a.set("fortification_gate")
                    form_b.set("open")
                    editor_buttons["Ajouter"].invoke()
                    root.update()
                    buttons["Enregistrer projet de jeu…"].invoke()
                    loaded = GameProject.load(project_file, Content.load(DEFAULT_CONTENT))
                    self.assertEqual(loaded.campaign_flow["gates"]["hold"],
                                     {"completed_mission": "garden"})
                    self.assertEqual(loaded.campaign_flow["outcomes"]["garden"]["victory"],
                                     [{"kind": "set_flag", "flag": "fortification_gate",
                                       "value": "open"}])
                    # Snapshot-based global history: one UI gesture = one record.
                    buttons["Annuler"].invoke()
                    root.update()
                    buttons["Rétablir"].invoke()
                    root.update()
                    buttons["Enregistrer projet de jeu…"].invoke()
                    reloaded = GameProject.load(project_file, Content.load(DEFAULT_CONTENT))
                    self.assertEqual(reloaded.to_dict(), loaded.to_dict())
                    self.assertEqual(callback_errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.filedialog.asksaveasfilename",
                       return_value=str(project_file)), \
                 patch("tkinter.messagebox.showerror") as errors:
                launch(DEFAULT_CONTENT)
                errors.assert_not_called()


if __name__ == "__main__":
    unittest.main()
