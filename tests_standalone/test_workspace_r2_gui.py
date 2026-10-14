"""R2 Tk/Xvfb gate — one Workspace inspector for two selected actors."""
import os
from unittest import TestCase, skipUnless
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
            'Requires Tk display')
class WorkspaceR2GuiTests(TestCase):
    def test_multi_actor_mixed_name_one_undo(self):
        import tkinter as tk
        from tkinter import ttk

        def children(node):
            for item in node.winfo_children():
                yield item
                yield from children(item)

        errors_in_callbacks = []

        def drive(root):
            try:
                root.report_callback_exception = (
                    lambda *args: errors_in_callbacks.append(args))
                root.update()
                notebook = next(w for w in children(root)
                                if isinstance(w, ttk.Notebook) and
                                'Espace projet' in [w.tab(t, 'text') for t in w.tabs()])
                tab = next(t for t in notebook.tabs()
                           if notebook.tab(t, 'text') == 'Espace projet')
                page = notebook.nametowidget(tab)
                notebook.select(tab)
                root.update()
                tree = next(w for w in children(page)
                            if isinstance(w, ttk.Treeview)
                            and w.exists('map_actor:garden/ziggy'))
                a, b = 'map_actor:garden/ziggy', 'map_actor:garden/momo'
                self.assertEqual(str(tree.cget('selectmode')), 'extended')
                tree.selection_set(a, b)
                tree.event_generate('<<TreeviewSelect>>')
                root.update()
                self.assertEqual(set(tree.selection()), {a, b})
                frame = next(w for w in children(page)
                             if isinstance(w, ttk.Labelframe) and
                             w.cget('text') == 'Propriétés éditables')
                field = next(w for w in children(frame)
                             if isinstance(w, ttk.Label) and
                             w.cget('text') == 'Nom *')
                entry = next(w for w in field.master.winfo_children()
                             if isinstance(w, ttk.Entry))
                self.assertEqual(entry.get(), '(mixte)')
                entry.delete(0, 'end')
                entry.insert(0, 'Escouade R2')
                apply = next(w for w in children(frame)
                             if isinstance(w, ttk.Button)
                             and w.cget('text') == 'Appliquer les propriétés')
                apply.invoke()
                root.update()
                self.assertIn('Escouade R2', tree.item(a, 'text'))
                self.assertIn('Escouade R2', tree.item(b, 'text'))
                undo = next(w for w in children(root)
                            if isinstance(w, ttk.Button)
                            and w.cget('text') == 'Annuler')
                undo.invoke()
                root.update()
                self.assertIn('Ziggy', tree.item(a, 'text'))
                self.assertIn('Momo', tree.item(b, 'text'))
                self.assertEqual(errors_in_callbacks, [])
            finally:
                root.destroy()

        with patch.object(tk.Tk, 'mainloop', drive), \
             patch('tkinter.messagebox.showerror') as showerror:
            launch(DEFAULT_CONTENT)
            showerror.assert_not_called()


    def test_problem_to_tactical_actor_reference_inline_repair(self):
        import json
        import tkinter as tk
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from tkinter import ttk
        from sporebound.model import Content

        def children(node):
            for widget in node.winfo_children():
                yield widget
                yield from children(widget)

        with TemporaryDirectory() as folder:
            data = Content.load(DEFAULT_CONTENT).to_dict()
            mission = next(m for m in data['missions'] if m['id'] == 'garden')
            trigger = mission['triggers'][0]
            trigger['actions'].append({'kind': 'despawn', 'unit': 'missing_r2_actor'})
            # A missing despawn target is a non-fatal authoring diagnostic.
            Content.from_dict(data)
            key = 'tactical_event:garden/' + trigger['id']
            location = Path(folder) / 'content.json'
            location.write_text(json.dumps(data), encoding='utf-8')
            errors_in_callbacks = []

            def drive(root):
                try:
                    root.report_callback_exception = (
                        lambda *args: errors_in_callbacks.append(args))
                    root.update()
                    notebooks = [w for w in children(root)
                                 if isinstance(w, ttk.Notebook)]
                    main = next(w for w in notebooks
                                if 'Espace projet' in
                                [w.tab(t, 'text') for t in w.tabs()])
                    bottom = next(w for w in notebooks
                                  if 'Problèmes' in
                                  [w.tab(t, 'text') for t in w.tabs()])
                    tab_id = next(t for t in bottom.tabs()
                                  if bottom.tab(t, 'text') == 'Problèmes')
                    bottom.select(tab_id)
                    root.update()
                    problems = next(w for w in children(bottom.nametowidget(tab_id))
                                    if isinstance(w, ttk.Treeview))
                    problem_row = next(i for i in problems.get_children('')
                                       if problems.item(i, 'values')[1] == key)
                    problems.selection_set(problem_row)
                    problems.event_generate('<Return>')
                    root.update()
                    self.assertEqual(main.tab(main.select(), 'text'),
                                     'Espace projet')
                    workspace = main.nametowidget(next(
                        t for t in main.tabs()
                        if main.tab(t, 'text') == 'Espace projet'))
                    tree = next(w for w in children(workspace)
                                if isinstance(w, ttk.Treeview) and w.exists(key))
                    self.assertIn(key, tree.selection())
                    inspector = next(w for w in children(workspace)
                                     if isinstance(w, ttk.Labelframe) and
                                     w.cget('text') == 'Propriétés éditables')
                    label = next(w for w in children(inspector)
                                 if isinstance(w, ttk.Label) and
                                 w.cget('text') == 'Référence acteur (despawn)')
                    editor = next(w for w in label.master.winfo_children()
                                  if isinstance(w, ttk.Combobox))
                    editor.set('ziggy')
                    apply = next(w for w in children(inspector)
                                 if isinstance(w, ttk.Button) and
                                 w.cget('text') == 'Appliquer les propriétés')
                    apply.invoke()
                    root.update()
                    self.assertFalse(any(
                        problems.item(i, 'values')[1] == key
                        for i in problems.get_children('')))
                    self.assertFalse(errors_in_callbacks, errors_in_callbacks)
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.messagebox.showerror') as showerror:
                launch(location)
                showerror.assert_not_called()


if __name__ == '__main__':
    import unittest
    unittest.main()
