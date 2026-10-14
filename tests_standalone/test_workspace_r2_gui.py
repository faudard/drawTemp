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


if __name__ == '__main__':
    import unittest
    unittest.main()
