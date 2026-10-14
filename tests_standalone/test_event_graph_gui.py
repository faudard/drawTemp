"""Xvfb contract: click graph, author trigger actions and save playable Content."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import traceback
from unittest.mock import patch
from tests_standalone.studio_gui_actions import save_as

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
                    # Show the authoring validation error at the failing step,
                    # instead of reporting an unhelpful empty graph.
                    self.assertFalse(callback_errors, [''.join(traceback.format_exception(*err)) for err in callback_errors])
                    self.assertFalse(show_error.called, show_error.call_args_list)
                    self.assertTrue(any('event_node_' in tag
                                        for item in event_graph.find_all()
                                        for tag in event_graph.gettags(item)))
                    event_box = next(w for w in widgets
                                     if isinstance(w, ttk.Combobox)
                                     and 'event_new' in tuple(w['values']))
                    self.assertEqual(event_box.get(), 'event_new')

                    # 3.1: edit secondary condition through the same graph tab.
                    buttons['+ ET'].invoke()
                    root.update()
                    condition_tree = next(w for w in widgets
                                          if isinstance(w, ttk.Treeview)
                                          and w.exists('when'))
                    self.assertEqual(condition_tree.item('when', 'text'),
                                     'Tick ≥ 10')
                    condition_tree.selection_set('when')
                    condition_tree.event_generate('<<TreeviewSelect>>')
                    root.update()
                    buttons['+ OU'].invoke()
                    root.update()
                    self.assertEqual(condition_tree.item('when', 'text'), 'OU')
                    self.assertTrue(condition_tree.exists('when.0'))
                    self.assertTrue(condition_tree.exists('when.1'))
                    condition_tree.selection_set('when.1')
                    condition_tree.event_generate('<<TreeviewSelect>>')
                    root.update()
                    buttons['↑ Nœud'].invoke()
                    root.update()
                    self.assertTrue(condition_tree.exists('when.0'))
                    self.assertFalse(callback_errors)

                    # 3.7.21C: the same graph exposes read-only contextual
                    # inspection and a real-engine preview, without saving.
                    self.assertIn('Tester avec le moteur', buttons)
                    buttons['Tester avec le moteur'].invoke()
                    root.update()
                    context_text = next(w for w in widgets if isinstance(w, tk.Text))
                    self.assertIn('APERÇU ISOLÉ', context_text.get('1.0', 'end'))
                    self.assertIn('Condition non satisfaite',
                                  context_text.get('1.0', 'end'))
                    self.assertEqual(context_text.cget('state'), 'disabled')
                    # The scene uses the shared isometric renderer on two
                    # disposable Battle states, without replacing the editor.
                    buttons['Vue isométrique avant/après'].invoke()
                    root.update()
                    comparisons = [w for w in descendants(root)
                                   if isinstance(w, tk.Toplevel)
                                   and w.title().startswith('Aperçu isométrique')]
                    self.assertEqual(len(comparisons), 1)
                    canvases = [w for w in descendants(comparisons[0])
                                if isinstance(w, tk.Canvas)]
                    self.assertEqual(len(canvases), 2)
                    self.assertTrue(all(w.find_all() for w in canvases))
                    comparisons[0].destroy()
                    scenario = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                    and 'Condition vraie' in tuple(w['values']))
                    scenario.set('Condition vraie')
                    buttons['Tester avec le moteur'].invoke()
                    root.update()
                    self.assertIn('Condition satisfaite',
                                  context_text.get('1.0', 'end'))
                    scenario.set('Condition fausse')
                    buttons['Tester avec le moteur'].invoke()
                    root.update()
                    self.assertIn('Condition non satisfaite',
                                  context_text.get('1.0', 'end'))
                    # 3.2: the same UI can preview an entire real-engine
                    # cascade without creating another simulator/editor.
                    self.assertIn('Simuler chaîne', buttons)
                    # 3.4: branch editing stays in the same studio inspector.
                    # This mission has no linked story: no fabricated option
                    # is offered until an author connects a real scene.
                    self.assertIn('Simuler branches', buttons)
                    self.assertIn('Lier au choix', buttons)
                    self.assertIn('Effacer choix', buttons)
                    self.assertIn('+ OU rejoindre', buttons)
                    self.assertIn('− OU retirer', buttons)
                    self.assertIn('+ Lier événement', buttons)
                    self.assertIn('− Délier événement', buttons)
                    scenario.set('Condition vraie')
                    buttons['Simuler chaîne'].invoke()
                    root.update()
                    self.assertIn('CASCADE ISOLÉE',
                                  context_text.get('1.0', 'end'))
                    self.assertIn('Déclenchés : event_new',
                                  context_text.get('1.0', 'end'))
                    self.assertFalse(callback_errors)
                    # 3.3: all debugger controls stay in the same Event Graph,
                    # preserve the Content and never claim an authenticated
                    # replay for an artificially prepared condition.
                    for label in ('Démarrer debug', 'Point d’arrêt',
                                  'Continuer debug', 'Pas suivant',
                                  'Inspecter condition', 'Arrêter debug'):
                        self.assertIn(label, buttons)
                    buttons['Démarrer debug'].invoke()
                    root.update()
                    buttons['Point d’arrêt'].invoke()
                    buttons['Continuer debug'].invoke()
                    root.update()
                    self.assertIn('POINT D’ARRÊT — avant effets : event_new',
                                  context_text.get('1.0', 'end'))
                    buttons['Inspecter condition'].invoke()
                    root.update()
                    self.assertIn('DIAGNOSTIC : event_new',
                                  context_text.get('1.0', 'end'))
                    buttons['Pas suivant'].invoke()
                    root.update()
                    self.assertIn('1. event_new', context_text.get('1.0', 'end'))
                    self.assertIn('Replay : NON ATTESTÉ',
                                  context_text.get('1.0', 'end'))
                    buttons['Arrêter debug'].invoke()
                    root.update()
                    self.assertFalse(callback_errors)
                    self.assertFalse(show_error.called)

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
                    save_as(root)
                    output = Content.load(saved_path)
                    trigger = next(e for e in output.missions['garden'].triggers
                                   if e['id'] == 'event_new')
                    self.assertEqual([a['kind'] for a in trigger['actions']],
                                     ['hazard', 'message'])
                    self.assertEqual(trigger['actions'][0]['pos'], [0, 0])
                    self.assertEqual(trigger['when']['any'][0]['condition'], 'tick')
                    self.assertFalse(callback_errors)
                    buttons['Éditeur par blocs'].invoke()
                    self.assertEqual(studio.tab(studio.select(), 'text'),
                                     'Événements par blocs')
                    studio.select(index)
                    root.update()
                    buttons['+ Cinématique tactique'].invoke()
                    root.update()
                    self.assertEqual(studio.tab(studio.select(), 'text'),
                                     'Cinématiques')
                    self.assertTrue(any(
                        isinstance(w, tk.Listbox)
                        and any('cin_event_new' in w.get(i)
                                for i in range(w.size()))
                        for w in descendants(root)))
                    self.assertFalse(callback_errors)
                    show_error.assert_not_called()
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
