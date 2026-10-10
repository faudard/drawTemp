"""Xvfb contract: click graph, author trigger actions and save playable Content."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Needs display or Xvfb')
class TacticalEventGraphGUITests(unittest.TestCase):
    def test_create_event_edit_action_reorder_and_save(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            saved_path = Path(folder) / 'with_events.json'
            callback_errors = []

            def drive(root):
                try:
                    root.report_callback_exception = (
                        lambda *errors: callback_errors.append(errors))
                    root.update()
                    notebooks = [w for w in descendants(root)
                                 if isinstance(w, ttk.Notebook)]
                    studio = next(w for w in notebooks
                                  if 'Graphe des événements' in
                                  [w.tab(t, 'text') for t in w.tabs()])
                    index = next(i for i in range(len(studio.tabs()))
                                 if studio.tab(i, 'text') == 'Graphe des événements')
                    studio.select(index)
                    root.update()
                    page = root.nametowidget(studio.select())
                    widgets = list(descendants(page))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    event_graph = next(w for w in widgets if isinstance(w, tk.Canvas))
                    # A mission without triggers legitimately has an empty
                    # graph. Validate that creating its first event draws a
                    # selectable condition/action node.
                    existing = any('event_node_' in tag
                                   for item in event_graph.find_all()
                                   for tag in event_graph.gettags(item))
                    self.assertFalse(existing)

                    buttons['Créer événement'].invoke()
                    root.update()
                    self.assertTrue(any('event_node_' in tag
                                        for item in event_graph.find_all()
                                        for tag in event_graph.gettags(item)))
                    event_box = next(w for w in widgets
                                     if isinstance(w, ttk.Combobox)
                                     and 'event_new' in tuple(w['values']))
                    self.assertEqual(event_box.get(), 'event_new')

                    action_box = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                      and 'queue_wave' in tuple(w['values']))
                    action_box.set('hazard')
                    # Hazard pos x,y defaults to 0,0 and power defaults to 4.
                    buttons['Ajouter'].invoke()
                    root.update()
                    actions = next(w for w in widgets if isinstance(w, tk.Listbox))
                    self.assertEqual(actions.size(), 2)
                    actions.selection_set(1)
                    actions.event_generate('<<ListboxSelect>>')
                    root.update()
                    buttons['↑'].invoke()
                    root.update()
                    all_buttons = {w.cget('text'): w for w in descendants(root)
                                   if isinstance(w, ttk.Button)}
                    all_buttons['Enregistrer sous'].invoke()
                    output = Content.load(saved_path)
                    trigger = next(e for e in output.missions['garden'].triggers
                                   if e['id'] == 'event_new')
                    self.assertEqual([a['kind'] for a in trigger['actions']],
                                     ['hazard', 'message'])
                    self.assertEqual(trigger['actions'][0]['pos'], [0, 0])
                    self.assertFalse(callback_errors)
                    buttons['Éditeur par blocs'].invoke()
                    self.assertEqual(studio.tab(studio.select(), 'text'),
                                     'Événements par blocs')
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(saved_path)), \
                 patch('tkinter.messagebox.showerror') as show_error:
                launch(DEFAULT_CONTENT)
                show_error.assert_not_called()


if __name__ == '__main__':
    unittest.main()
