"""Tk regression for 2.5.1 selection/clipboard/zone gestures (Xvfb)."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk + virtual or actual display')
class MapEditorGUITests(unittest.TestCase):
    def test_select_copy_preview_paste_save_and_undo(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for widget in parent.winfo_children():
                yield widget
                yield from descendants(widget)

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / 'maps.json'
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    tool = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                and 'Sélection' in w.cget('values'))
                    brush = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                 and 'zone+' in w.cget('values'))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}

                    brush.set('wall')
                    canvas.event_generate('<Button-1>', x=70, y=70)
                    canvas.event_generate('<ButtonRelease-1>', x=70, y=70)
                    root.update()

                    tool.set('Sélection')
                    canvas.event_generate('<Button-1>', x=70, y=70)
                    canvas.event_generate('<B1-Motion>', x=124, y=70, state=256)
                    canvas.event_generate('<ButtonRelease-1>', x=124, y=70)
                    root.update()
                    buttons['Copier cases'].invoke()
                    root.update()

                    tool.set('Collage')
                    canvas.event_generate('<Motion>', x=232, y=286)
                    root.update()
                    self.assertTrue(canvas.find_withtag('paste_preview'))
                    canvas.event_generate('<Button-1>', x=232, y=286)
                    canvas.event_generate('<ButtonRelease-1>', x=232, y=286)
                    root.update()
                    buttons['Enregistrer sous'].invoke()
                    saved = json.loads(target.read_text(encoding='utf-8'))
                    tiles = {tuple(t['pos']): t for t in saved['missions'][0]['board']['tiles']}
                    self.assertTrue(tiles[(4, 5)]['blocked'])
                    self.assertFalse(tiles.get((5, 5), {}).get('blocked', False))
                    buttons['Annuler'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    undone = json.loads(target.read_text(encoding='utf-8'))
                    tiles = {tuple(t['pos']): t for t in undone['missions'][0]['board']['tiles']}
                    self.assertFalse(tiles.get((4, 5), {}).get('blocked', False))
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename', return_value=str(target)), \
                 patch('tkinter.messagebox.showerror') as dialog_error:
                launch(DEFAULT_CONTENT)
                dialog_error.assert_not_called()

    def test_deployment_zone_click_uses_full_validation(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for widget in parent.winfo_children():
                yield widget
                yield from descendants(widget)

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / 'zones.json'
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    brush = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                 and 'zone+' in w.cget('values'))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    brush.set('zone+')
                    canvas.event_generate('<Button-1>', x=20, y=20)
                    canvas.event_generate('<ButtonRelease-1>', x=20, y=20)
                    buttons['Enregistrer sous'].invoke()
                    saved = json.loads(target.read_text(encoding='utf-8'))
                    zone = saved['missions'][0]['deployment'][0]
                    self.assertEqual(zone['id'], 'attackers')
                    self.assertIn([0, 0], zone['cells'])
                    self.assertIn([1, 5], zone['cells'])  # initial hero remains deployable
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename', return_value=str(target)), \
                 patch('tkinter.messagebox.showerror') as dialog_error:
                launch(DEFAULT_CONTENT)
                dialog_error.assert_not_called()

    def test_rotated_stamp_minimap_and_group_movement(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / 'rotated.json'
            stamp_path = Path(tmp) / 'stair.stamp.json'
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *err: errors.append(err)
                    root.update()
                    widgets = list(descendants(root))
                    canvases = [w for w in widgets if isinstance(w, tk.Canvas)]
                    # Map canvas is the first canvas constructed by the editor.
                    main_canvas = canvases[0]
                    # The minimap has a full tactical overview (184x184).
                    mini = next(w for w in canvases if int(w.cget('width')) == 184)
                    self.assertTrue(mini.find_all())
                    tool = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                and 'Sélection' in w.cget('values'))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    tool.set('Sélection')
                    main_canvas.event_generate('<Button-1>', x=182, y=182)
                    main_canvas.event_generate('<B1-Motion>', x=236, y=182, state=256)
                    main_canvas.event_generate('<ButtonRelease-1>', x=236, y=182)
                    root.update()
                    buttons['Copier cases'].invoke()
                    buttons['↻ 90°'].invoke()
                    buttons['Sauver modèle'].invoke()
                    self.assertTrue(stamp_path.exists())
                    stamp = json.loads(stamp_path.read_text(encoding='utf-8'))
                    self.assertEqual(stamp['size'], [1, 2])
                    buttons['Charger modèle'].invoke()
                    main_canvas.event_generate('<Motion>', x=290, y=20)
                    root.update()
                    self.assertTrue(main_canvas.find_withtag('paste_preview'))
                    main_canvas.event_generate('<Button-1>', x=290, y=20)
                    main_canvas.event_generate('<ButtonRelease-1>', x=290, y=20)
                    root.update()
                    tool.set('Sélection')
                    main_canvas.event_generate('<Button-1>', x=128, y=20)
                    main_canvas.event_generate('<ButtonRelease-1>', x=128, y=20)
                    root.update()
                    buttons['→'].invoke()  # Move chest without changing its ID.
                    buttons['Enregistrer sous'].invoke()
                    saved = json.loads(target.read_text(encoding='utf-8'))
                    mission = saved['missions'][0]
                    tiles = {tuple(t['pos']): t for t in mission['board']['tiles']}
                    self.assertTrue(tiles[(5, 0)]['blocked'])
                    self.assertEqual(tiles[(5, 1)]['height'], 1)
                    self.assertEqual(next(o for o in mission['objects'] if
                                          o['id'] == 'chest')['pos'], [3, 0])
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       side_effect=[str(stamp_path), str(target)]), \
                 patch('tkinter.filedialog.askopenfilename',
                       return_value=str(stamp_path)), \
                 patch('tkinter.simpledialog.askstring',
                       return_value='Escalier'), \
                 patch('tkinter.messagebox.showerror') as dialog_error:
                launch(DEFAULT_CONTENT)
                dialog_error.assert_not_called()


if __name__ == '__main__':
    unittest.main()
