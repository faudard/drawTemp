"""Tk/Xvfb acceptance for Map Builder 4.0C layer locks and active levels."""
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
from sporebound.interior_levels import add_interior_floor
from sporebound.iso_structures import place_structure
from sporebound.map_layer_workspace import load_views, view_for
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk with a real screen or Xvfb')
class LayerWorkspaceGuiTests(unittest.TestCase):
    def test_toggle_lock_change_level_and_restore_without_touching_player_content(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'map_content.json'
            data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                     'layer_smoke', 'Layer Smoke', 16, 16)
            data = place_structure(data, 'layer_smoke', 'Maison', (4, 4))
            mid = next(m for m in data['missions'] if m['id'] == 'layer_smoke')
            data = add_interior_floor(data, 'layer_smoke',
                                      mid['structures'][0]['id'], 1)
            path.write_text(json.dumps(data), encoding='utf-8')
            popups, failures = [], []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *error: failures.append(error)
                    root.update()
                    all_widgets = list(descendants(root))
                    canvas = next(w for w in all_widgets if isinstance(w, tk.Canvas))
                    roof = next(w for w in all_widgets if isinstance(w, ttk.Checkbutton)
                                and w.cget('text') == 'Toitures')
                    lock_button = next(w for w in all_widgets
                                       if isinstance(w, ttk.Menubutton)
                                       and w.cget('text') == 'Verrouiller couches ▾')
                    menu = root.nametowidget(lock_button.cget('menu'))
                    levels = next(w for w in all_widgets if isinstance(w, ttk.Combobox)
                                  and '0' in w.cget('values') and '3' in w.cget('values')
                                  and len(w.cget('values')) == 4)
                    buttons = {w.cget('text'): w for w in all_widgets
                               if isinstance(w, ttk.Button)}
                    mission_box = next(w for w in all_widgets
                                       if isinstance(w, ttk.Combobox)
                                       and 'layer_smoke' in w.cget('values'))
                    mission_box.set('layer_smoke')
                    mission_box.event_generate('<<ComboboxSelected>>')
                    root.update()
                    roof.invoke()
                    root.update()
                    menu.invoke(menu.index('Terrain'))
                    root.update()
                    canvas.event_generate('<Button-1>', x=9*54+10, y=9*54+10)
                    canvas.event_generate('<ButtonRelease-1>', x=9*54+10, y=9*54+10)
                    root.update()
                    self.assertTrue(popups, 'Locked terrain must show an error')
                    before_save = json.loads(path.read_text(encoding='utf-8'))
                    original_tile = {tuple(t['pos']): t for t in
                                     before_save['missions'][-1]['board']['tiles']}
                    self.assertNotIn((9, 9), original_tile)
                    menu.invoke(menu.index('Terrain'))
                    root.update()
                    canvas.event_generate('<Button-1>', x=9*54+10, y=9*54+10)
                    canvas.event_generate('<ButtonRelease-1>', x=9*54+10, y=9*54+10)
                    root.update()
                    levels.set('1')
                    levels.event_generate('<<ComboboxSelected>>')
                    root.update()
                    save_as(root)
                    saved = json.loads(path.read_text(encoding='utf-8'))
                    tiles = {tuple(t['pos']): t for t in
                             saved['missions'][-1]['board']['tiles']}
                    self.assertTrue(tiles[(9, 9)]['blocked'])
                    views = load_views(path)
                    state = view_for(views, 'layer_smoke')
                    self.assertFalse(state['visible']['Toitures'])
                    self.assertFalse(state['locked']['Terrain'])
                    self.assertEqual(state['active_level'], 1)
                    self.assertTrue(state['interiors'])
                    self.assertTrue(Content.from_dict(saved))
                    self.assertEqual(failures, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(path)), \
                 patch('tkinter.messagebox.showerror',
                       side_effect=lambda *a: popups.append(a)):
                launch(path)


if __name__ == '__main__':
    unittest.main()
