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

                toolbars = [w for w in descendants(root)
                            if isinstance(w, ttk.Notebook)
                            and 'Terrain & couches' in
                            [w.tab(t, 'text') for t in w.tabs()]]
                self.assertEqual(len(toolbars), 1)
                self.assertEqual(
                    [toolbars[0].tab(t, 'text') for t in toolbars[0].tabs()],
                    ['Carte & combat', 'Terrain & couches',
                     'Architecture', 'Sélection & modèles'])
                self.assertTrue(any(
                    isinstance(w, ttk.Menubutton) and
                    'Autres couches' in w.cget('text')
                    for w in descendants(root)))
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
                self.assertTrue(any(w.get() == 'escape' for w in descendants(root)
                                    if isinstance(w, ttk.Combobox)),
                                'Navigating the sidebar must change the active mission')

                buttons = {w.cget('text'): w for w in descendants(root)
                           if isinstance(w, ttk.Button)}
                self.assertIn('Espace projet complet', buttons)
                self.assertIn('Modifier le personnage sélectionné', buttons)
                self.assertIn('Modifier l’objet sélectionné', buttons)
                self.assertEqual(str(buttons[
                    'Modifier le personnage sélectionné'].cget('state')),
                    'disabled')
                self.assertEqual(str(buttons[
                    'Modifier l’objet sélectionné'].cget('state')),
                    'disabled')
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
                self.assertEqual(
                    toolbars[0].tab(toolbars[0].select(), 'text'),
                    'Carte & combat')
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

    def test_map_selection_opens_exact_actor_and_object_form(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for widget in parent.winfo_children():
                yield widget
                yield from descendants(widget)

        def drive(root):
            try:
                root.update()
                top = next(w for w in descendants(root)
                           if isinstance(w, ttk.Notebook)
                           and 'Carte et combat' in
                           [w.tab(t, 'text') for t in w.tabs()])
                page = next(t for t in top.tabs()
                            if top.tab(t, 'text') == 'Carte et combat')
                shell = top.nametowidget(page)
                middle = shell.nametowidget(shell.panes()[1])
                map_frame = middle.nametowidget(middle.panes()[0])
                canvas = next(w for w in descendants(map_frame)
                              if isinstance(w, tk.Canvas))
                tool_box = next(w for w in descendants(root)
                                if isinstance(w, ttk.Combobox) and
                                'Sélection' in w.cget('values'))
                tool_box.set('Sélection')
                buttons = {w.cget('text'): w for w in descendants(root)
                           if isinstance(w, ttk.Button)}

                # garden's Ziggy starts on (1, 5) and switch on (2, 4).
                for x, y, title, editor_page, entity_id in (
                    (1, 5, 'Modifier le personnage sélectionné',
                     'Personnages / monstres', 'ziggy'),
                    (2, 4, 'Modifier l’objet sélectionné',
                     'Objets interactifs', 'switch')
                ):
                    top.select(page)
                    root.update()
                    canvas.event_generate('<Button-1>',
                                          x=x * 54 + 12, y=y * 54 + 12)
                    canvas.event_generate('<ButtonRelease-1>',
                                          x=x * 54 + 12, y=y * 54 + 12)
                    root.update()
                    self.assertEqual(str(buttons[title].cget('state')), 'normal')
                    buttons[title].invoke()
                    root.update()
                    self.assertEqual(top.tab(top.select(), 'text'),
                                     'Personnages et événements')
                    subtab = next(w for w in descendants(root)
                                  if isinstance(w, ttk.Notebook)
                                  and editor_page in
                                  [w.tab(t, 'text') for t in w.tabs()])
                    self.assertEqual(subtab.tab(subtab.select(), 'text'),
                                     editor_page)
                    selected = [w.get(i) for w in descendants(subtab)
                                if isinstance(w, tk.Listbox)
                                for i in w.curselection()]
                    self.assertTrue(any(v.startswith(entity_id + '  —  ')
                                        for v in selected))
            finally:
                root.destroy()

        with patch.object(tk.Tk, 'mainloop', drive), \
             patch('tkinter.messagebox.showerror') as errors:
            launch(DEFAULT_CONTENT)
            errors.assert_not_called()
