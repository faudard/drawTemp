"""Optional Tk smoke for 3.7.31 — actual Workspace -> map + docked panels.

Run with SPOREBOUND_GUI_SMOKE=1 on Xvfb or a desktop.
"""
import os
from unittest import TestCase, skipUnless
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1', 'Tk display required')
class WorkspaceShellGUITests(TestCase):
    def test_resource_navigation_and_problem_dock(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(node):
            for child in node.winfo_children():
                yield child
                yield from descendants(child)

        def drive(root):
            try:
                root.update()
                books = [w for w in descendants(root) if isinstance(w, ttk.Notebook)]
                main = next(w for w in books if 'Carte et combat' in
                            [w.tab(page, 'text') for page in w.tabs()])
                bottom = next(w for w in books if 'Problèmes' in
                              [w.tab(page, 'text') for page in w.tabs()])
                names = [bottom.tab(page, 'text') for page in bottom.tabs()]
                self.assertTrue({'Problèmes', 'Historique', 'Console',
                                 'Simulation'} <= set(names))
                problems = next(page for page in bottom.tabs()
                                if bottom.tab(page, 'text') == 'Problèmes')
                bottom.select(problems)
                root.update()
                self.assertTrue(any(isinstance(w, ttk.Treeview)
                                    for w in descendants(bottom.nametowidget(problems))))

                project = next(page for page in main.tabs()
                               if main.tab(page, 'text') == 'Espace projet')
                main.select(project)
                root.update()
                tree = next(w for w in descendants(main.nametowidget(project))
                            if isinstance(w, ttk.Treeview)
                            and w.exists('map_object:garden/switch'))
                tree.selection_set('map_object:garden/switch')
                tree.focus('map_object:garden/switch')
                tree.focus_set()
                root.update()
                tree.event_generate('<Return>')
                root.update()
                self.assertFalse(errors.call_args_list, errors.call_args_list)
                self.assertEqual(main.tab(main.select(), 'text'), 'Carte et combat')
                map_page = next(page for page in main.tabs()
                                if main.tab(page, 'text') == 'Carte et combat')
                texts = [w.get('1.0', 'end-1c') for w in
                         descendants(main.nametowidget(map_page))
                         if isinstance(w, tk.Text)]
                self.assertTrue(any('switch' in value.lower() and
                                    '(2, 4)' in value for value in texts))
            finally:
                root.destroy()

        with patch.object(tk.Tk, 'mainloop', drive), \
             patch('tkinter.messagebox.showerror') as errors:
            launch(DEFAULT_CONTENT)
            errors.assert_not_called()
