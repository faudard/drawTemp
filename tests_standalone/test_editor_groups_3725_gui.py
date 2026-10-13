"""Tk/Xvfb smoke gate: hierarchical group Treeview, preview and undo."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document, launch
from sporebound.editor_groups import create_editor_group
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk/Xvfb')
class EditorGroupGUITests(unittest.TestCase):
    def test_tree_preview_move_undo_and_create_empty(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for item in parent.winfo_children():
                yield item
                yield from descendants(item)

        with TemporaryDirectory() as folder:
            mid = 'editor_groups_gui'
            data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                     mid, 'Groupes', 20, 20)
            doc = Document(Content.from_dict(data))
            doc.paint_many(mid, [(4, 4)], 'feature:tree')
            group_data = create_editor_group(doc.data, mid, 'Bosquet',
                                             cells=((4, 4),))
            source = Path(folder) / 'input.json'
            target = Path(folder) / 'out.json'
            source.write_text(json.dumps(group_data), encoding='utf-8')
            errors = []

            def state():
                mission = next(m for m in json.loads(
                    target.read_text(encoding='utf-8'))['missions']
                    if m['id'] == mid)
                return mission

            def drive(root):
                try:
                    root.report_callback_exception = lambda *error: errors.append(error)
                    root.update()
                    widgets = list(descendants(root))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    trees = [w for w in widgets if isinstance(w, ttk.Treeview)]
                    hierarchy = next(w for w in trees if w.exists('g:group_1'))
                    missions = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                    and mid in w.cget('values'))
                    missions.set(mid)
                    missions.event_generate('<<ComboboxSelected>>')
                    root.update()
                    hierarchy.selection_set('g:group_1')
                    hierarchy.event_generate('<<TreeviewSelect>>')
                    root.update()
                    self.assertTrue(hierarchy.exists('g:group_1'))
                    buttons['Aperçu'].invoke()
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    self.assertTrue(canvas.find_withtag('editor_group_preview'))
                    buttons['Déplacer'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(state()['editor_groups'][0]['cells'],
                                     [[5, 4]])
                    self.assertTrue(any(t['pos'] == [5, 4] and
                                        t['feature'] == 'tree'
                                        for t in state()['board']['tiles']))
                    buttons['Annuler'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(state()['editor_groups'][0]['cells'],
                                     [[4, 4]])
                    buttons['Créer vide'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(len(state()['editor_groups']), 2)
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(target)), \
                 patch('tkinter.simpledialog.askstring', return_value='Nouvelle zone'), \
                 patch('tkinter.messagebox.showerror') as error:
                launch(source)
                error.assert_not_called()


if __name__ == '__main__':
    unittest.main()
