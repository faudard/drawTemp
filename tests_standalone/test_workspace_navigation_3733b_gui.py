"""3.7.33B — Tk/Xvfb selection sync, breadcrumbs and back/forward smoke."""
import os
from unittest import TestCase, skipUnless
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
            'Run under Tk/Xvfb')
class WorkspaceNavigationGuiTests(TestCase):
    def test_tree_preview_history_and_map_selection_roundtrip(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        callback_errors = []

        def drive(root):
            try:
                root.report_callback_exception = (
                    lambda *args: callback_errors.append(args))
                root.update()
                main = next(w for w in descendants(root)
                            if isinstance(w, ttk.Notebook) and
                            'Espace projet' in
                            [w.tab(tab, 'text') for tab in w.tabs()])
                workspace_tab = next(tab for tab in main.tabs()
                                     if main.tab(tab, 'text') == 'Espace projet')
                workspace = main.nametowidget(workspace_tab)
                main.select(workspace_tab)
                root.update()
                tree = next(w for w in descendants(workspace)
                            if isinstance(w, ttk.Treeview)
                            and w.exists('map_actor:garden/ziggy'))
                previous = next(w for w in descendants(workspace)
                                if isinstance(w, ttk.Button)
                                and w.cget('text') == '← Précédent')
                following = next(w for w in descendants(workspace)
                                 if isinstance(w, ttk.Button)
                                 and w.cget('text') == 'Suivant →')
                tree.selection_set('map_actor:garden/ziggy')
                tree.event_generate('<<TreeviewSelect>>')
                root.update()
                self.assertEqual(main.tab(main.select(), 'text'),
                                 'Espace projet')
                breadcrumb = next(w for w in descendants(workspace)
                                  if isinstance(w, ttk.Label)
                                  and w.cget('textvariable') and
                                  str(root.getvar(w.cget('textvariable'))).startswith(
                                      'Projet / '))
                self.assertIn('ziggy', root.getvar(breadcrumb.cget('textvariable')).lower())

                tree.selection_set('map_object:garden/switch')
                tree.event_generate('<<TreeviewSelect>>')
                root.update()
                self.assertIn('switch', tree.selection())
                previous.invoke()
                root.update()
                self.assertIn('map_actor:garden/ziggy', tree.selection())
                following.invoke()
                root.update()
                self.assertIn('map_object:garden/switch', tree.selection())

                # A live map click in Selection mode updates the same project
                # Treeview without opening a second inspector or duplicating
                # resource history entries.
                map_tab = next(tab for tab in main.tabs()
                               if main.tab(tab, 'text') == 'Carte et combat')
                main.select(map_tab)
                shell = main.nametowidget(map_tab)
                middle = shell.nametowidget(shell.panes()[1])
                canvas_area = middle.nametowidget(middle.panes()[0])
                canvas = next(w for w in descendants(canvas_area)
                              if isinstance(w, tk.Canvas))
                tool = next(w for w in descendants(root)
                            if isinstance(w, ttk.Combobox)
                            and 'Sélection' in w.cget('values'))
                tool.set('Sélection')
                root.update()
                canvas.event_generate('<Button-1>', x=1*54+12, y=5*54+12)
                canvas.event_generate('<ButtonRelease-1>',
                                      x=1*54+12, y=5*54+12)
                root.update()
                self.assertEqual(tree.selection(), ('map_actor:garden/ziggy',))
                self.assertEqual(callback_errors, [])
            finally:
                root.destroy()

        with patch.object(tk.Tk, 'mainloop', drive), \
             patch('tkinter.messagebox.showerror') as errors:
            launch(DEFAULT_CONTENT)
            errors.assert_not_called()


if __name__ == '__main__':
    import unittest
    unittest.main()
