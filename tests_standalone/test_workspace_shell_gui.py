"""Tk smoke tests for the resizable 3.7.21A authoring workspace.

Run with SPOREBOUND_GUI_SMOKE=1 under Xvfb (or a real display).
"""
import os
from unittest import TestCase, skipUnless
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1', 'Requires a Tk display')
class WorkspaceShellGUITests(TestCase):
    def test_docked_project_browser_and_contextual_inspector(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for widget in parent.winfo_children():
                yield widget
                yield from descendants(widget)

        def drive(root):
            try:
                root.update()
                main = next(w for w in descendants(root)
                            if isinstance(w, ttk.Notebook)
                            and 'Carte et combat' in
                            [w.tab(t, 'text') for t in w.tabs()])
                page = next(t for t in main.tabs()
                            if main.tab(t, 'text') == 'Carte et combat')
                shell = main.nametowidget(page)
                self.assertIsInstance(shell, ttk.Panedwindow)
                self.assertEqual(str(shell.cget('orient')), 'horizontal')
                self.assertEqual(len(shell.panes()), 3)

                middle = shell.nametowidget(shell.panes()[1])
                self.assertIsInstance(middle, ttk.Panedwindow)
                self.assertEqual(str(middle.cget('orient')), 'vertical')
                self.assertEqual(len(middle.panes()), 2)

                map_trees = [w for w in descendants(shell)
                             if isinstance(w, ttk.Treeview)]
                navigator = next(w for w in map_trees
                                 if w.exists('mission:garden'))
                self.assertTrue(navigator.exists('mission:escape'))
                self.assertTrue(navigator.exists('group:campaign'))
                navigator.selection_set('mission:escape')
                navigator.event_generate('<Return>')
                root.update()
                self.assertEqual(main.tab(main.select(), 'text'), 'Carte et combat')

                buttons = {w.cget('text'): w for w in descendants(root)
                           if isinstance(w, ttk.Button)}
                self.assertIn('Espace projet complet', buttons)
                self.assertIn('Éditer personnages et objets', buttons)
                mode_labels = [
                    w for w in descendants(shell)
                    if isinstance(w, ttk.Label)
                    and w.cget('textvariable')
                    and str(root.getvar(w.cget('textvariable'))).startswith('MODE : ')
                ]
                self.assertEqual(len(mode_labels), 1)
                mode = lambda: root.getvar(mode_labels[0].cget('textvariable'))
                self.assertIn('ÉDITION', mode())
                buttons['Playtest'].invoke()
                root.update()
                self.assertIn('PLAYTEST', mode())
                buttons['Éditer'].invoke()
                root.update()
                self.assertIn('ÉDITION', mode())

                buttons['Espace projet complet'].invoke()
                self.assertEqual(main.tab(main.select(), 'text'), 'Espace projet')
            finally:
                root.destroy()

        with patch.object(tk.Tk, 'mainloop', drive), \
             patch('tkinter.messagebox.showerror') as errors:
            launch(DEFAULT_CONTENT)
            errors.assert_not_called()
