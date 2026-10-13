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


    def test_drag_drop_reparents_groups_and_transfers_objects_and_cells(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.authoring import add_object

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            mid = 'editor_groups_dnd'
            data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                     mid, 'Arbre', 20, 20)
            data = add_object(data, mid, 'crate1', 'chest', (8, 8))
            data = create_editor_group(data, mid, 'A',
                                       cells=((4, 4), (5, 4), (8, 8)))
            data = create_editor_group(data, mid, 'B')
            data = create_editor_group(data, mid, 'Enfant', parent='group_1')
            source = Path(folder) / 'in.json'
            output = Path(folder) / 'out.json'
            source.write_text(json.dumps(data), encoding='utf-8')
            errors = []

            def mission():
                return next(m for m in json.loads(
                    output.read_text(encoding='utf-8'))['missions']
                    if m['id'] == mid)

            def drive(root):
                try:
                    root.report_callback_exception = lambda *error: errors.append(error)
                    root.update()
                    widgets = list(descendants(root))
                    hierarchy = next(w for w in widgets if
                                     isinstance(w, ttk.Treeview) and
                                     w.exists('g:group_1'))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    missions = next(w for w in widgets
                                    if isinstance(w, ttk.Combobox)
                                    and mid in w.cget('values'))
                    missions.set(mid)
                    missions.event_generate('<<ComboboxSelected>>')
                    root.update()

                    def center(iid):
                        hierarchy.see(iid)
                        root.update()
                        x, y, w, h = hierarchy.bbox(iid)
                        self.assertGreater(w, 0)
                        return x + max(14, w // 2), y + h // 2

                    def drop(start, destination):
                        ax, ay = center(start)
                        bx, by = center(destination)
                        hierarchy.event_generate('<ButtonPress-1>', x=ax, y=ay)
                        root.update()
                        hierarchy.event_generate('<B1-Motion>', x=bx, y=by,
                                                 state=0x100)
                        hierarchy.event_generate('<ButtonRelease-1>', x=bx,
                                                 y=by)
                        root.update()

                    # Reparent group_3 from A to B, without moving terrain.
                    drop('g:group_3', 'g:group_2')
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(mission()['editor_groups'][2]['parent'],
                                     'group_2')
                    # A cycle must not modify the document or emit a popup.
                    drop('g:group_2', 'g:group_3')
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(mission()['editor_groups'][1]['parent'], None)

                    # Transfer the exact object leaf to B.
                    drop('m:group_1:object_ids:crate1', 'g:group_2')
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(mission()['editor_groups'][1]['object_ids'],
                                     ['crate1'])
                    self.assertEqual(mission()['objects'][0]['pos'], [8, 8])

                    # Unlink that object by dropping it onto the virtual root.
                    drop('m:group_2:object_ids:crate1', 'root:groups')
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(mission()['editor_groups'][1]['object_ids'],
                                     [])
                    buttons['Annuler'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(mission()['editor_groups'][1]['object_ids'],
                                     ['crate1'])
                    buttons['Rétablir'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(mission()['editor_groups'][1]['object_ids'],
                                     [])

                    # Expand the lazy decorative tile nodes; drag one tile only.
                    hierarchy.focus('cells:group_1')
                    hierarchy.item('cells:group_1', open=True)
                    hierarchy.event_generate('<<TreeviewOpen>>')
                    root.update()
                    self.assertTrue(hierarchy.exists('t:group_1:4:4'))
                    drop('t:group_1:4:4', 'g:group_2')
                    buttons['Enregistrer sous'].invoke()
                    groups = mission()['editor_groups']
                    self.assertIn([4, 4], groups[1]['cells'])
                    self.assertNotIn([4, 4], groups[0]['cells'])
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(output)), \
                 patch('tkinter.messagebox.showerror') as dialog:
                launch(source)
                dialog.assert_not_called()


    def test_multi_select_duplicate_preview_save_and_undo(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            mid = 'editor_group_multi_gui'
            data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                     mid, 'Copie groupes', 20, 20)
            data = create_editor_group(data, mid, 'Arbre', cells=((3, 3),))
            data = create_editor_group(data, mid, 'Place', cells=((7, 7),))
            source = Path(folder) / 'input.json'
            output = Path(folder) / 'output.json'
            source.write_text(json.dumps(data), encoding='utf-8')
            errors = []

            def read_groups():
                mission = next(m for m in json.loads(
                    output.read_text(encoding='utf-8'))['missions']
                    if m['id'] == mid)
                return mission['editor_groups']

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    widgets = list(descendants(root))
                    hierarchy = next(w for w in widgets
                                     if isinstance(w, ttk.Treeview)
                                     and w.exists('g:group_1'))
                    self.assertEqual(hierarchy.cget('selectmode'), 'extended')
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    missions = next(w for w in widgets
                                    if isinstance(w, ttk.Combobox)
                                    and mid in w.cget('values'))
                    missions.set(mid)
                    missions.event_generate('<<ComboboxSelected>>')
                    root.update()

                    hierarchy.selection_set(('g:group_1', 'g:group_2'))
                    hierarchy.event_generate('<<TreeviewSelect>>')
                    root.update()
                    self.assertEqual(len(hierarchy.selection()), 2)
                    buttons['Aperçu copie'].invoke()
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    self.assertTrue(canvas.find_withtag('editor_group_preview'))
                    buttons['Dupliquer groupes'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    groups = read_groups()
                    self.assertEqual(len(groups), 4)
                    self.assertEqual([g['cells'] for g in groups[-2:]],
                                     [[[4, 3]], [[8, 7]]])
                    self.assertEqual(len({g['id'] for g in groups}), 4)
                    buttons['Annuler'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(len(read_groups()), 2)
                    buttons['Rétablir'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(len(read_groups()), 4)
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(output)), \
                 patch('tkinter.messagebox.showerror') as dialog:
                launch(source)
                dialog.assert_not_called()


if __name__ == '__main__':
    unittest.main()
