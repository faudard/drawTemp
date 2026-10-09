"""Smoke checks for the guided Tk studio and title/campaign workflow.

Run under Xvfb with SPOREBOUND_GUI_SMOKE=1.
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires a Tk display')
class StudioGUITests(unittest.TestCase):
    def test_guided_forms_project_save_and_campaign_slot(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            destination=Path(folder)/'created.game.json'
            errors=[]

            def drive(root):
                try:
                    root.report_callback_exception=lambda *exc: errors.append(exc)
                    root.update()
                    widgets=list(descendants(root))
                    notebooks=[w for w in widgets if isinstance(w,ttk.Notebook)]
                    self.assertTrue(any(len(w.tabs()) >= 5 for w in notebooks))
                    buttons={w.cget('text'):w for w in widgets if isinstance(w,ttk.Button)}
                    buttons['Créer événement sur la case'].invoke()
                    root.update()
                    buttons['Nouvelle partie'].invoke()
                    root.update()
                    buttons['Enregistrer projet de jeu…'].invoke()
                    self.assertTrue(destination.is_file())
                    self.assertEqual(json.loads(destination.read_text(encoding='utf-8'))['version'],1)
                    buttons['Enregistrer partie'].invoke()
                    self.assertTrue((Path(folder)/'created.game_saves'/'main'/'slot_1.json').is_file())
                    buttons['Charger partie'].invoke()
                    buttons['Jouer campagne'].invoke()
                    root.update()
                    self.assertEqual(errors,[])
                finally:
                    root.destroy()

            with patch.object(tk.Tk,'mainloop',drive), \
                 patch('tkinter.filedialog.asksaveasfilename',return_value=str(destination)), \
                 patch('tkinter.messagebox.showerror') as dialog_error:
                launch(DEFAULT_CONTENT)
                dialog_error.assert_not_called()


if __name__=='__main__':
    unittest.main()
