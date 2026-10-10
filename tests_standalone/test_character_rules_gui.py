"""Xvfb smoke for Character & Rules Studio 3.0 (real Tk and Content save)."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'A Tk/Xvfb display is required')
class CharacterRulesGUITests(unittest.TestCase):
    def test_character_skill_job_and_equipment_authoring_with_save(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            path = Path(folder) / 'character_rules.json'
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *args: errors.append(args)
                    root.update()
                    all_widgets = list(descendants(root))
                    notebook = next(widget for widget in all_widgets
                                    if isinstance(widget, ttk.Notebook)
                                    and 'Personnages & règles 3.0' in [
                                        widget.tab(tab, 'text')
                                        for tab in widget.tabs()])
                    parent_tab = next(i for i in range(len(notebook.tabs()))
                                      if notebook.tab(i, 'text') ==
                                      'Personnages & règles 3.0')
                    notebook.select(parent_tab)
                    root.update()
                    page = root.nametowidget(notebook.select())
                    inner = next(widget for widget in descendants(page)
                                 if isinstance(widget, ttk.Notebook))
                    self.assertEqual(
                        [inner.tab(tab, 'text') for tab in inner.tabs()],
                        ['Héros / monstres', 'Archétypes', 'Compétences',
                         'Classes', 'Équipement'])

                    def open_tab(name):
                        idx = next(i for i in range(len(inner.tabs()))
                                   if inner.tab(i, 'text') == name)
                        inner.select(idx)
                        root.update()
                        return root.nametowidget(inner.select())

                    def buttons(tab):
                        return {w.cget('text'): w for w in descendants(tab)
                                if isinstance(w, ttk.Button)}

                    skills = open_tab('Compétences')
                    controls = list(descendants(skills))
                    chooser = next(w for w in controls if isinstance(w, ttk.Combobox)
                                   and 'flare' in tuple(w['values']))
                    chooser.set('guided_bolt')
                    buttons(skills)['Créer compétence'].invoke()
                    root.update()
                    self.assertIn('guided_bolt', tuple(chooser['values']))
                    buttons(skills)['Ajouter effet'].invoke()
                    root.update()
                    effect_list = next(w for w in controls if isinstance(w, tk.Listbox))
                    self.assertEqual(effect_list.size(), 2)

                    classes = open_tab('Classes')
                    class_chooser = next(w for w in descendants(classes)
                                         if isinstance(w, ttk.Combobox)
                                         and 'brave' in tuple(w['values']))
                    class_chooser.set('guided_knight')
                    buttons(classes)['Créer classe'].invoke()
                    root.update()
                    self.assertIn('guided_knight', tuple(class_chooser['values']))

                    equipment = open_tab('Équipement')
                    item_chooser = next(w for w in descendants(equipment)
                                        if isinstance(w, ttk.Combobox)
                                        and 'mycelium_plate' in tuple(w['values']))
                    item_chooser.set('guided_ring')
                    buttons(equipment)['Créer équipement'].invoke()
                    root.update()
                    self.assertIn('guided_ring', tuple(item_chooser['values']))

                    units = open_tab('Héros / monstres')
                    unit_chooser = next(w for w in descendants(units)
                                        if isinstance(w, ttk.Combobox)
                                        and 'ziggy' in tuple(w['values']))
                    unit_chooser.set('ziggy')
                    unit_chooser.event_generate('<<ComboboxSelected>>')
                    root.update()
                    buttons(units)['Appliquer personnage'].invoke()
                    root.update()

                    top_buttons = {w.cget('text'):w for w in descendants(root)
                                   if isinstance(w,ttk.Button)}
                    top_buttons['Enregistrer sous'].invoke()
                    saved = Content.load(path)
                    self.assertIn('guided_bolt', saved.skills)
                    self.assertEqual(len(saved.skills['guided_bolt'].effects), 2)
                    self.assertIn('guided_knight', saved.jobs)
                    self.assertIn('guided_ring', saved.equipment)
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(path)), \
                 patch('tkinter.messagebox.showerror') as show_error:
                launch(DEFAULT_CONTENT)
                show_error.assert_not_called()


if __name__ == '__main__':
    unittest.main()
