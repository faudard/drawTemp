"""Tk/Xvfb authoring: class prereq, talent DAG and tactical patrol route."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk/Xvfb')
class ClassAIGUITests(unittest.TestCase):
    def test_talent_graph_class_link_and_patrol_are_saved(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            destination = Path(tmp) / 'class_ai.json'
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *args: errors.append(args)
                    root.update()
                    notebooks = [w for w in descendants(root)
                                 if isinstance(w, ttk.Notebook)]
                    main = next(w for w in notebooks
                                if 'Personnages & règles 3.0' in
                                [w.tab(tab, 'text') for tab in w.tabs()])
                    main.select(next(i for i in range(len(main.tabs()))
                                     if main.tab(i, 'text') == 'Personnages & règles 3.0'))
                    root.update()
                    page = root.nametowidget(main.select())
                    sub = next(w for w in descendants(page)
                               if isinstance(w, ttk.Notebook))

                    def select_tab(label):
                        index = next(i for i in range(len(sub.tabs()))
                                     if sub.tab(i, 'text') == label)
                        sub.select(index)
                        root.update()
                        return root.nametowidget(sub.select())

                    def buttons(frame):
                        return {w.cget('text'):w for w in descendants(frame)
                                if isinstance(w, ttk.Button)}

                    class_page = select_tab('Graphe des classes')
                    self.assertEqual(len([w for w in descendants(class_page)
                                          if isinstance(w, tk.Canvas)]),2)
                    talent_box = next(w for w in descendants(class_page)
                                      if isinstance(w, ttk.Combobox)
                                      and str(w.cget('state')) == 'normal')
                    talent_box.set('pathfinder_talent')
                    buttons(class_page)['Créer talent'].invoke()
                    root.update()

                    combos = [w for w in descendants(class_page)
                              if isinstance(w, ttk.Combobox)]
                    class_box = next(w for w in combos
                                     if 'field_medic' in tuple(w['values']))
                    class_box.set('field_medic')
                    class_box.event_generate('<<ComboboxSelected>>')
                    root.update()
                    prior = next(w for w in combos
                                 if w is not class_box and
                                 'bulwark' in tuple(w['values']))
                    prior.set('bulwark')
                    buttons(class_page)['Relier / retirer le prérequis'].invoke()
                    root.update()

                    ai_page = select_tab('IA & patrouilles')
                    ai_boxes = [w for w in descendants(ai_page)
                                if isinstance(w,ttk.Combobox)]
                    unit_box = next(w for w in ai_boxes
                                    if 'grincheux' in tuple(w['values']))
                    unit_box.set('grincheux')
                    unit_box.event_generate('<<ComboboxSelected>>')
                    root.update()
                    entries = [w for w in descendants(ai_page)
                               if type(w) is ttk.Entry]
                    self.assertEqual(len(entries),2)
                    entries[0].delete(0,'end')
                    entries[0].insert(0,'protector')
                    entries[1].delete(0,'end')
                    entries[1].insert(0,'2,1; 4,1')
                    buttons(ai_page)['Appliquer IA et route'].invoke()
                    root.update()

                    saves = buttons(root)
                    saves['Enregistrer sous'].invoke()
                    loaded = Content.load(destination)
                    self.assertIn('pathfinder_talent',loaded.jobs['brave']['talents'])
                    self.assertEqual(loaded.jobs['field_medic']['requires'],'bulwark')
                    actor = next(u for u in loaded.missions['garden'].units
                                 if u.id=='grincheux')
                    self.assertEqual(actor.tags,['protector'])
                    self.assertEqual(actor.patrol_route, ((2,1),(4,1)))
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk,'mainloop',drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(destination)), \
                 patch('tkinter.messagebox.showerror') as show_error:
                launch(DEFAULT_CONTENT)
                show_error.assert_not_called()


if __name__=='__main__':
    unittest.main()
