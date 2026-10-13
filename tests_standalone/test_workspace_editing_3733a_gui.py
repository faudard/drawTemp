"""3.7.33A — actual Workspace inline edit + global Undo/Redo in Tk/Xvfb."""
import os
from unittest import TestCase, skipUnless
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1', 'Requires Tk display')
class WorkspaceInspectorGuiTests(TestCase):
    def test_edit_actor_name_inline_then_global_undo(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(node):
            for child in node.winfo_children():
                yield child
                yield from descendants(child)

        errors_in_callback = []

        def drive(root):
            try:
                root.report_callback_exception = lambda *args: errors_in_callback.append(args)
                root.update()
                notebooks = [w for w in descendants(root)
                             if isinstance(w, ttk.Notebook)]
                main = next(w for w in notebooks if 'Espace projet' in
                            [w.tab(t, 'text') for t in w.tabs()])
                page = main.nametowidget(next(
                    t for t in main.tabs() if main.tab(t, 'text') == 'Espace projet'))
                main.select(page)
                root.update()
                tree = next(w for w in descendants(page)
                            if isinstance(w, ttk.Treeview)
                            and w.exists('map_actor:garden/ziggy'))
                tree.selection_set('map_actor:garden/ziggy')
                root.update()
                frame = next(w for w in descendants(page)
                             if isinstance(w, ttk.Labelframe)
                             and w.cget('text') == 'Propriétés éditables')

                def name_entry():
                    label = next(w for w in descendants(frame)
                                 if isinstance(w, ttk.Label)
                                 and w.cget('text') == 'Nom')
                    return next(w for w in label.master.winfo_children()
                                if isinstance(w, ttk.Entry))

                original = name_entry().get()
                name_entry().delete(0, 'end')
                name_entry().insert(0, 'Ziggy Workspace')
                apply = next(w for w in descendants(frame)
                             if isinstance(w, ttk.Button)
                             and w.cget('text') == 'Appliquer les propriétés')
                apply.invoke()
                root.update()
                self.assertEqual(name_entry().get(), 'Ziggy Workspace')
                buttons = {w.cget('text'): w for w in descendants(root)
                           if isinstance(w, ttk.Button)}
                buttons['Annuler'].invoke()
                root.update()
                self.assertEqual(name_entry().get(), original)
                self.assertFalse(errors_in_callback, errors_in_callback)
            finally:
                root.destroy()

        with patch.object(tk.Tk, 'mainloop', drive), \
             patch('tkinter.messagebox.showerror') as errors:
            launch(DEFAULT_CONTENT)
            errors.assert_not_called()


if __name__ == '__main__':
    import unittest
    unittest.main()
