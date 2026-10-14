"""Tk/Xvfb acceptance: suggested quarter preview is non-destructive, then undoable."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import launch
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk + virtual display')
class QuarterGeneratorGUITests(unittest.TestCase):
    def test_generate_preview_confirm_save_undo(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(node):
            for child in node.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            source = Path(folder) / 'quarter_studio.json'
            saved = Path(folder) / 'quarter_saved.json'
            raw = add_blank_mission(
                Content.load(DEFAULT_CONTENT).to_dict(),
                'quarter_gui_3732e', 'Quarter GUI', 40, 40)
            source.write_text(json.dumps(raw), encoding='utf-8')
            errors = []
            popups = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    widgets = list(descendants(root))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    missions = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                    and 'quarter_gui_3732e' in w.cget('values'))
                    styles = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                  and 'Fortifié' in w.cget('values')
                                  and 'Marché' in w.cget('values'))
                    variants = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                    and 'Variante 3' in w.cget('values'))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    tool = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                and 'Pinceau' in w.cget('values')
                                and 'Sélection' in w.cget('values'))
                    missions.set('quarter_gui_3732e')
                    missions.event_generate('<<ComboboxSelected>>')
                    root.update()
                    styles.set('Marché')
                    buttons['Générer 3 variantes'].invoke()
                    root.update()
                    variants.set('Variante 2')
                    variants.event_generate('<<ComboboxSelected>>')
                    root.update()
                    # Select without painting a wall under the prospective quarter.
                    tool.set('Sélection')
                    canvas.event_generate('<Button-1>', x=10*54+10, y=10*54+10)
                    canvas.event_generate('<ButtonRelease-1>', x=10*54+10, y=10*54+10)
                    root.update()
                    buttons['Aperçu des différences'].invoke()
                    root.update()
                    self.assertTrue(canvas.find_withtag('quarter_generation_preview'))
                    self.assertNotIn('editor_groups',
                                     next(m for m in raw['missions']
                                          if m['id'] == 'quarter_gui_3732e'))
                    buttons['Enregistrer comme préfab'].invoke()
                    self.assertTrue(list((Path(folder) / 'prefabs').glob('*.json')))
                    buttons['Confirmer placement'].invoke()
                    root.update()
                    buttons['Enregistrer sous'].invoke()
                    result = json.loads(saved.read_text(encoding='utf-8'))
                    scene = next(m for m in result['missions']
                                 if m['id'] == 'quarter_gui_3732e')
                    self.assertEqual(len(scene['editor_groups']), 5)
                    self.assertEqual(len(scene['objects']), 1)
                    self.assertTrue(Content.from_dict(result))
                    buttons['Annuler'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    undone = json.loads(saved.read_text(encoding='utf-8'))
                    scene = next(m for m in undone['missions']
                                 if m['id'] == 'quarter_gui_3732e')
                    self.assertFalse(scene.get('editor_groups'))
                    self.assertFalse(scene['objects'])
                    self.assertEqual(errors, [])
                    self.assertEqual(popups, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(saved)), \
                 patch('tkinter.messagebox.showerror',
                       side_effect=lambda *args: popups.append(args)):
                launch(source)


if __name__ == '__main__':
    unittest.main()
