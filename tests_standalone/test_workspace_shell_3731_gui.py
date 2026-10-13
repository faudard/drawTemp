"""Optional Tk smoke for 3.7.31 — actual Workspace -> map + docked panels.

Run with SPOREBOUND_GUI_SMOKE=1 on Xvfb or a desktop.
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch
from sporebound.authoring import add_object
from sporebound.model import Content


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

    def test_problem_navigation_fix_and_live_resolution_without_manual_refresh(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(node):
            for child in node.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            original = Content.load(DEFAULT_CONTENT)
            mission = original.missions['garden']
            occupied = {tuple(obj['pos']) for obj in mission.objects}
            occupied.update(c for actor in mission.units for c in actor.occupied_cells())
            free = [cell for cell in mission.board.cells()
                    if cell not in occupied and not mission.board.tile(cell).blocked]
            self.assertGreaterEqual(len(free), 2)
            door_cell, lever_cell = free[:2]
            door_id = 'workspace_gate_3731'
            key = f'map_object:garden/{door_id}'
            content_path = Path(tmp) / 'workspace_3731.json'
            data = add_object(original.to_dict(), 'garden', door_id,
                              'door', door_cell)
            content_path.write_text(json.dumps(data), encoding='utf-8')

            callback_errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *args: callback_errors.append(args)
                    root.update()
                    notebooks = [w for w in descendants(root)
                                 if isinstance(w, ttk.Notebook)]
                    main = next(w for w in notebooks if 'Carte et combat' in
                                [w.tab(t, 'text') for t in w.tabs()])
                    bottom = next(w for w in notebooks if 'Problèmes' in
                                  [w.tab(t, 'text') for t in w.tabs()])
                    tab = next(t for t in bottom.tabs()
                               if bottom.tab(t, 'text') == 'Problèmes')
                    bottom.select(tab)
                    root.update()
                    problems = next(w for w in descendants(bottom.nametowidget(tab))
                                    if isinstance(w, ttk.Treeview))
                    orphan = next(i for i in problems.get_children('')
                                  if problems.item(i, 'values')[1] == key)
                    problems.selection_set(orphan)
                    problems.focus(orphan)
                    problems.focus_set()
                    root.update()
                    problems.event_generate('<Return>')
                    root.update()
                    self.assertFalse(errors.call_args_list, errors.call_args_list)
                    self.assertEqual(main.tab(main.select(), 'text'), 'Carte et combat')
                    map_page = main.nametowidget(next(
                        t for t in main.tabs() if main.tab(t, 'text') == 'Carte et combat'))
                    texts = [w.get('1.0', 'end-1c') for w in descendants(map_page)
                             if isinstance(w, tk.Text)]
                    self.assertTrue(any(door_id in t and str(door_cell) in t
                                        for t in texts))

                    # Fix the reference through the existing Entities editor.
                    tool = next(w for w in descendants(root)
                                if isinstance(w, ttk.Combobox)
                                and 'Sélection' in w.cget('values'))
                    tool.set('Sélection')
                    middle = map_page.nametowidget(map_page.panes()[1])
                    frame = middle.nametowidget(middle.panes()[0])
                    canvas = next(w for w in descendants(frame)
                                  if isinstance(w, tk.Canvas))
                    canvas.xview_moveto(0)
                    canvas.yview_moveto(0)
                    root.update()
                    x, y = lever_cell
                    canvas.event_generate('<Button-1>', x=x * 54 + 12, y=y * 54 + 12)
                    canvas.event_generate('<ButtonRelease-1>',
                                          x=x * 54 + 12, y=y * 54 + 12)
                    root.update()

                    entity_tabs = next(w for w in descendants(root)
                                       if isinstance(w, ttk.Notebook)
                                       and 'Objets interactifs' in
                                       [w.tab(t, 'text') for t in w.tabs()])
                    object_page = entity_tabs.nametowidget(next(
                        t for t in entity_tabs.tabs()
                        if entity_tabs.tab(t, 'text') == 'Objets interactifs'))
                    fields = {
                        row: object_page.grid_slaves(row=row, column=1)[0]
                        for row in (0, 1, 2)
                    }
                    fields[0].delete(0, 'end')
                    fields[0].insert(0, 'workspace_lever_3731')
                    fields[1].set('switch')
                    fields[2].delete(0, 'end')
                    fields[2].insert(0, door_id)
                    button = next(w for w in descendants(object_page)
                                  if isinstance(w, ttk.Button)
                                  and w.cget('text') == 'Placer sur la carte')
                    button.invoke()
                    root.update()
                    self.assertFalse(any(
                        problems.item(i, 'values')[1] == key
                        for i in problems.get_children('')),
                        'A corrected reference must disappear without manual refresh.')
                    self.assertEqual(callback_errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.messagebox.showerror') as errors:
                launch(content_path)
                errors.assert_not_called()
