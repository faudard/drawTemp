"""B1.2 Xvfb smoke: click the rendered roof and facade, not a tile combobox."""
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
from sporebound.building_visuals import edit_building_appearance
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk and Xvfb')
class BuildingVisualGuiTests(unittest.TestCase):
    def test_select_real_roof_then_facade_and_undo_window(self):
        import tkinter as tk
        from tkinter import ttk

        def walk(parent):
            for child in parent.winfo_children():
                yield child
                yield from walk(child)

        with TemporaryDirectory() as folder:
            path = Path(folder) / 'visual.json'
            raw = Content.load(DEFAULT_CONTENT).to_dict()
            raw = add_blank_mission(raw, 'building_visual_b12',
                                    'Building direct selection', 16, 16)
            raw = place_structure(raw, 'building_visual_b12', 'Maison', (4, 4))
            sid = next(m['structures'][0]['id'] for m in raw['missions']
                       if m['id'] == 'building_visual_b12')
            # Authored appearance forces the editable vector facade/roof,
            # whereas unmodified buildings may use a single atlas PNG.
            raw = edit_building_appearance(
                raw, 'building_visual_b12', sid, facade='pierre',
                roof='tuiles')
            path.write_text(json.dumps(raw), encoding='utf-8')
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    widgets = list(walk(root))
                    mission = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                   and 'building_visual_b12' in w.cget('values'))
                    mission.set('building_visual_b12')
                    mission.event_generate('<<ComboboxSelected>>')
                    root.update()
                    projection = next(w for w in widgets
                                      if isinstance(w, ttk.Radiobutton)
                                      and w.cget('text') == 'Iso 2.5D')
                    projection.invoke()
                    root.update()
                    navigation = next(w for w in widgets
                                      if isinstance(w, ttk.Radiobutton)
                                      and w.cget('text') == 'Bâtiments')
                    navigation.invoke()
                    root.update()
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas)
                                  and w.find_withtag('architecture_roof'))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    add = buttons['Ajouter une fenêtre à ce mur']
                    remove = buttons['Supprimer cette fenêtre']

                    def click_item(tag):
                        ids = canvas.find_withtag(tag)
                        self.assertTrue(ids, 'Missing rendered item: ' + tag)
                        item = next(i for i in ids
                                    if len(canvas.coords(i)) >= 6)
                        coords = canvas.coords(item)
                        pairs = list(zip(coords[::2], coords[1::2]))
                        cx = sum(x for x, _ in pairs) / len(pairs)
                        cy = sum(y for _, y in pairs) / len(pairs)
                        region = list(map(float, canvas.cget('scrollregion').split()))
                        left, top, right, bottom = region
                        ww = max(canvas.winfo_width(), 1)
                        hh = max(canvas.winfo_height(), 1)
                        if right > left:
                            canvas.xview_moveto(max(0, min(1,
                                (cx - ww/2 - left) / (right-left))))
                        if bottom > top:
                            canvas.yview_moveto(max(0, min(1,
                                (cy - hh/2 - top) / (bottom-top))))
                        root.update()
                        x, y = int(cx - canvas.canvasx(0)), int(cy - canvas.canvasy(0))
                        canvas.event_generate('<Button-1>', x=x, y=y)
                        canvas.event_generate('<ButtonRelease-1>', x=x, y=y)
                        root.update()

                    click_item('architecture_roof')
                    self.assertTrue(add.instate(['disabled']))
                    click_item('architecture_facade')
                    self.assertFalse(add.instate(['disabled']))
                    add.invoke()
                    root.update()
                    save_as(root)
                    saved = Content.load(path).to_dict()
                    row = next(m['structures'][0] for m in saved['missions']
                               if m['id'] == 'building_visual_b12')
                    self.assertEqual(len(row['appearance']['windows']), 1)
                    self.assertFalse(remove.instate(['disabled']))
                    remove.invoke()
                    root.update()
                    save_as(root)
                    saved = Content.load(path).to_dict()
                    row = next(m['structures'][0] for m in saved['missions']
                               if m['id'] == 'building_visual_b12')
                    self.assertEqual(row['appearance']['windows'], [])
                    self.assertFalse(errors, errors)
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
