"""Tk condition builder smoke: visual groups, runtime preview and saved manifest."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch
from sporebound.game_project import GameProject
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires a display or Xvfb')
class ConditionBuilderGUITests(unittest.TestCase):
    def test_add_boolean_group_preview_save_undo_and_graph_navigation(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            output = Path(folder) / 'conditions.game.json'
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    all_widgets = list(descendants(root))
                    book = next(w for w in all_widgets if isinstance(w, ttk.Notebook)
                                and 'Conditions & variables' in
                                [w.tab(tab, 'text') for tab in w.tabs()])
                    tab = next(i for i in range(len(book.tabs()))
                               if book.tab(i, 'text') == 'Conditions & variables')
                    book.select(tab)
                    root.update()
                    page = root.nametowidget(book.select())
                    children = list(descendants(page))
                    scene = next(w for w in children if isinstance(w, ttk.Combobox)
                                 and 'council' in tuple(w['values']))
                    scene.set('council')
                    scene.event_generate('<<ComboboxSelected>>')
                    root.update()
                    choice = next(w for w in children if isinstance(w, ttk.Combobox)
                                  and 'relic' in tuple(w['values']))
                    choice.set('relic')
                    choice.event_generate('<<ComboboxSelected>>')
                    root.update()
                    tree = next(w for w in children if isinstance(w, ttk.Treeview))
                    self.assertTrue(tree.get_children())
                    buttons = {w.cget('text'): w for w in all_widgets
                               if isinstance(w, ttk.Button)}
                    buttons['ET'].invoke()
                    root.update()
                    self.assertGreaterEqual(len(tree.get_children('p0')), 1)
                    preset = next(w for w in children if isinstance(w, ttk.Combobox)
                                  and 'flag ≥' in tuple(w['values']))
                    preset.set('flag ≥')
                    # ttk.Combobox inherits ttk.Entry; exclude its selectors.
                    entries = [w for w in children if type(w) is ttk.Entry]
                    # Find the variables and value entries using their Tk textvariable.
                    variable = entries[0]  # Condition key, not preview flag
                    value = entries[1]  # Condition value, regardless of selected preset
                    variable.delete(0, 'end')
                    variable.insert(0, 'trust')
                    value.delete(0, 'end')
                    value.insert(0, '2')
                    buttons['+ enfant'].invoke()
                    root.update()
                    self.assertEqual(len(tree.get_children('p0')), 2)
                    preview_flags = entries[4]
                    preview_flags.delete(0, 'end')
                    preview_flags.insert(0, 'trust=2')
                    preview_gold = entries[5]  # Preview field, not an arbitrary zero
                    preview_gold.delete(0, 'end')
                    preview_gold.insert(0, '150')
                    self.assertEqual(preview_flags.get(), 'trust=2')
                    self.assertEqual(preview_gold.get(), '150')
                    buttons['Enregistrer projet de jeu…'].invoke()
                    debug_saved = GameProject.load(output, Content.load(DEFAULT_CONTENT))
                    debug_council = next(sc for sc in debug_saved.story['scenes']
                                         if sc['id'] == 'council')
                    debug_relic = next(ch for ch in debug_council['choices']
                                       if ch['id'] == 'relic')
                    self.assertEqual(debug_relic.get('when'), {
                        'all': [{'gold_gte': 100},
                                {'flag': 'trust', 'gte': 2}]})
                    buttons['Tester la condition'].invoke()
                    statuses = [w.getvar(w.cget('textvariable'))
                                for w in children if isinstance(w, ttk.Label)
                                and str(w.cget('textvariable'))]
                    self.assertTrue(any('VISIBLE' in str(status)
                                        for status in statuses),
                                    (statuses, [w.get() for w in entries]))
                    buttons['Enregistrer projet de jeu…'].invoke()
                    saved = GameProject.load(output, Content.load(DEFAULT_CONTENT))
                    council = next(s for s in saved.story['scenes'] if s['id'] == 'council')
                    relic = next(c for c in council['choices'] if c['id'] == 'relic')
                    self.assertEqual(relic['when']['all'][0], {'gold_gte': 100})
                    self.assertEqual(relic['when']['all'][1], {'flag': 'trust', 'gte': 2})
                    buttons['Annuler scénario'].invoke()
                    root.update()
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(output)), \
                 patch('tkinter.messagebox.showerror') as dialog_error:
                launch(DEFAULT_CONTENT)
                dialog_error.assert_not_called()


if __name__ == '__main__':
    unittest.main()
