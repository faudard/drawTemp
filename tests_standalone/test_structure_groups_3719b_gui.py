"""Tk/Xvfb gate for rectangle-selected structure group manipulation."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import launch
from sporebound.iso_structures import place_structure
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk/Xvfb')
class StructureGroupGestures(unittest.TestCase):
    def test_rectangle_preview_move_clone_and_undo(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            mid = 'structure_group_gui'
            base = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                     mid, 'Atelier', 20, 20)
            base = place_structure(base, mid, 'Maison', (2, 1))
            base = place_structure(base, mid, 'Tour', (6, 1))
            input_file = Path(tmp) / 'input.json'
            output_file = Path(tmp) / 'output.json'
            input_file.write_text(json.dumps(base), encoding='utf-8')
            errors = []

            def records():
                doc = json.loads(output_file.read_text(encoding='utf-8'))
                return next(row for row in doc['missions']
                            if row['id'] == mid)['structures']

            def set_spinbox(widget, value):
                widget.delete(0, 'end')
                widget.insert(0, str(value))

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    tool = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                and 'Sélection structure' in w.cget('values'))
                    missions = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                    and mid in w.cget('values'))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    spinboxes = [w for w in widgets if isinstance(w, ttk.Spinbox)]
                    self.assertGreaterEqual(len(spinboxes), 3)
                    group_x, group_y = spinboxes[1:3]
                    missions.set(mid)
                    missions.event_generate('<<ComboboxSelected>>')
                    root.update()
                    tool.set('Sélection')
                    canvas.event_generate('<Button-1>', x=135, y=81)
                    canvas.event_generate('<B1-Motion>', x=459, y=189,
                                          state=0x100)
                    canvas.event_generate('<ButtonRelease-1>', x=459, y=189)
                    root.update()
                    buttons['Aperçu groupe'].invoke()
                    self.assertTrue(canvas.find_withtag('structure_group_preview'))
                    buttons['Déplacer groupe'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    moved = records()
                    self.assertEqual({tuple(row['anchor']) for row in moved},
                                     {(3, 1), (7, 1)})
                    self.assertEqual(len({row['id'] for row in moved}), 2)
                    buttons['Annuler'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual({tuple(row['anchor']) for row in records()},
                                     {(2, 1), (6, 1)})
                    buttons['Rétablir'].invoke()
                    set_spinbox(group_x, 0)
                    set_spinbox(group_y, 5)
                    buttons['Dupliquer groupe'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(len(records()), 4)
                    self.assertEqual(len({row['id'] for row in records()}), 4)
                    self.assertEqual({tuple(row['anchor']) for row in records()},
                                     {(3, 1), (7, 1), (3, 6), (7, 6)})
                    buttons['Annuler'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(len(records()), 2)
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(output_file)), \
                 patch('tkinter.messagebox.showerror') as dialog:
                launch(input_file)
                dialog.assert_not_called()


if __name__ == '__main__':
    unittest.main()
