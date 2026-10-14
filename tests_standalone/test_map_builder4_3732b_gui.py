"""Tk/Xvfb smoke for Map Builder 4.0B visual building details."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tests_standalone.studio_gui_actions import save_as

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import launch
from sporebound.iso_structures import place_structure
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk + Xvfb/desktop display')
class VisualArchitectureGuiTests(unittest.TestCase):
    def test_house_window_roof_facade_round_trip(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(w):
            for child in w.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            path = Path(folder) / 'content.json'
            raw = Content.load(DEFAULT_CONTENT).to_dict()
            raw = add_blank_mission(raw, 'facade_smoke', 'Facade smoke', 16, 16)
            raw = place_structure(raw, 'facade_smoke', 'Maison', (4, 4))
            path.write_text(json.dumps(raw), encoding='utf-8')
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *e: errors.append(e)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    tool = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                and 'Fenêtre façade' in w.cget('values'))
                    facade = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                  and 'torchis' in w.cget('values'))
                    roof = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                and 'ardoise' in w.cget('values'))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}

                    def click(x, y):
                        canvas.event_generate('<Button-1>', x=x, y=y)
                        canvas.event_generate('<ButtonRelease-1>', x=x, y=y)
                        root.update()

                    mission = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                   and 'facade_smoke' in w.cget('values'))
                    mission.set('facade_smoke')
                    mission.event_generate('<<ComboboxSelected>>')
                    root.update()
                    # Architectural controls live in the Building dock,
                    # never in the map's permanent tool strip.
                    self.assertFalse(buttons['Poser fenêtre'].winfo_ismapped())
                    self.assertTrue(buttons['Poser fenêtre'].instate(['disabled']))
                    self.assertTrue(buttons['Appliquer façade/toiture'].instate(['disabled']))
                    building_nav = next(
                        w for w in widgets if isinstance(w, ttk.Radiobutton)
                        and w.cget('text') == 'Bâtiments')
                    building_nav.invoke()
                    root.update()
                    self.assertTrue(building_nav.instate(['selected']))
                    self.assertTrue(canvas.winfo_ismapped())
                    tool.set('Sélection structure')
                    click(4*54+10, 4*54+10)
                    self.assertFalse(buttons['Poser fenêtre'].instate(['disabled']))
                    self.assertFalse(buttons['Appliquer façade/toiture'].instate(['disabled']))
                    building_tabs = next(
                        w for w in widgets if isinstance(w, ttk.Notebook)
                        and 'Extérieur' in [w.tab(t, 'text') for t in w.tabs()]
                        and 'Intérieur' in [w.tab(t, 'text') for t in w.tabs()])
                    exterior = next(t for t in building_tabs.tabs()
                                    if building_tabs.tab(t, 'text') == 'Extérieur')
                    building_tabs.select(exterior)
                    root.update()
                    self.assertTrue(buttons['Poser fenêtre'].winfo_ismapped())
                    facade.set('brique')
                    roof.set('plat')
                    buttons['Appliquer façade/toiture'].invoke()
                    root.update()
                    buttons['Poser fenêtre'].invoke()
                    click(4*54+10, 5*54+10)
                    save_as(root)
                    saved = json.loads(path.read_text(encoding='utf-8'))
                    authored = next(m for m in saved['missions']
                                    if m['id'] == 'facade_smoke')
                    house = authored['structures'][0]
                    self.assertEqual(house['appearance'],
                                     {'facade': 'brique', 'roof': 'plat',
                                      'windows': [[0, 1]]})
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(path)), \
                 patch('tkinter.messagebox.showerror') as popup:
                launch(path)
                popup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
