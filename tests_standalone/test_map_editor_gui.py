"""Tk regression for 2.5.1 selection/clipboard/zone gestures (Xvfb)."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tests_standalone.studio_gui_actions import save_as

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
                    save_as(root)
                    saved = json.loads(target.read_text(encoding='utf-8'))
                    tiles = {tuple(t['pos']): t for t in saved['missions'][0]['board']['tiles']}
                    self.assertTrue(tiles[(4, 5)]['blocked'])
                    self.assertFalse(tiles.get((5, 5), {}).get('blocked', False))
                    buttons['Annuler'].invoke()
                    save_as(root)
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
                    save_as(root)
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
                    mini = next(w for w in canvases if w.winfo_pixels(w.cget('width')) == 184)
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
                    save_as(root)
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


    def test_isometric_preview_can_paint_a_surface_by_click(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.iso_map import IsoGeometry
        from sporebound.model import Content

        def descendants(parent):
            for widget in parent.winfo_children():
                yield widget
                yield from descendants(widget)

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'isometric.json'
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *err: errors.append(err)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    toggle = next(w for w in widgets if isinstance(w, ttk.Radiobutton)
                                  and w.cget('text') == 'Iso 2.5D')
                    surface = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                   and 'bridge' in w.cget('values'))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    toggle.invoke()
                    self.assertTrue(any(canvas.type(item) == 'image'
                                        for item in canvas.find_all()))
                    surface.set('stone')
                    surface.event_generate('<<ComboboxSelected>>')
                    root.update()
                    board = next(iter(Content.load(DEFAULT_CONTENT).missions.values())).board
                    geo = IsoGeometry(board, 54)
                    pos = (3, 3)
                    px, py = geo.center(pos)
                    canvas.xview_moveto(max(0.0, (px - canvas.winfo_width()/2)/geo.width))
                    canvas.yview_moveto(max(0.0, (py - canvas.winfo_height()/2)/geo.height))
                    root.update()
                    x, y = int(px-canvas.canvasx(0)), int(py-canvas.canvasy(0))
                    self.assertTrue(0 <= x < canvas.winfo_width())
                    self.assertTrue(0 <= y < canvas.winfo_height())
                    canvas.event_generate('<Button-1>', x=x, y=y)
                    canvas.event_generate('<ButtonRelease-1>', x=x, y=y)
                    root.update()
                    feature = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                   and 'arch' in w.cget('values'))
                    feature.set('arch')
                    feature.event_generate('<<ComboboxSelected>>')
                    canvas.event_generate('<Button-1>', x=x, y=y)
                    canvas.event_generate('<ButtonRelease-1>', x=x, y=y)
                    root.update()
                    self.assertTrue(canvas.find_withtag('decor_sprite'))
                    save_as(root)
                    saved = json.loads(output.read_text(encoding='utf-8'))
                    tile = next(t for t in saved['missions'][0]['board']['tiles']
                                if t['pos'] == [3, 3])
                    self.assertEqual(tile['surface'], 'stone')
                    self.assertEqual(tile['feature'], 'arch')
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename', return_value=str(output)), \
                 patch('tkinter.messagebox.showerror') as dialog_error:
                launch(DEFAULT_CONTENT)
                dialog_error.assert_not_called()



    def test_flood_fill_and_eyedroppers_in_orthographic_and_iso_modes(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.iso_map import IsoGeometry
        from sporebound.model import Content

        def descendants(parent):
            for widget in parent.winfo_children():
                yield widget
                yield from descendants(widget)

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'fill.json'
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *err: errors.append(err)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    tool = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                and 'Remplissage' in w.cget('values'))
                    brush = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                 and 'zone+' in w.cget('values'))
                    surface = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                   and 'bridge' in w.cget('values'))
                    feature = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                   and 'arch' in w.cget('values'))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}

                    def click(x, y):
                        canvas.event_generate('<Button-1>', x=x, y=y)
                        canvas.event_generate('<ButtonRelease-1>', x=x, y=y)
                        root.update()

                    surface.set('stone')
                    surface.event_generate('<<ComboboxSelected>>')
                    root.update()
                    click(4*54+12, 4*54+12)
                    click(5*54+12, 4*54+12)
                    surface.set('dirt')
                    surface.event_generate('<<ComboboxSelected>>')
                    buttons['Remplir sol'].invoke()
                    click(4*54+12, 4*54+12)
                    buttons['Pipette sol'].invoke()
                    click(4*54+12, 4*54+12)
                    self.assertEqual(brush.get(), 'surface:dirt')
                    self.assertEqual(tool.get(), 'Pinceau')

                    feature.set('arch')
                    feature.event_generate('<<ComboboxSelected>>')
                    click(6*54+12, 4*54+12)
                    buttons['Pipette décor'].invoke()
                    click(6*54+12, 4*54+12)
                    self.assertEqual(brush.get(), 'feature:arch')
                    buttons['Pipette décor'].invoke()
                    click(4*54+12, 4*54+12)
                    self.assertEqual(brush.get(), 'feature-erase')

                    toggle = next(w for w in widgets if isinstance(w, ttk.Radiobutton)
                                  and w.cget('text') == 'Iso 2.5D')
                    toggle.invoke()
                    root.update()
                    board = next(iter(Content.load(DEFAULT_CONTENT).missions.values())).board
                    geo = IsoGeometry(board, 54)
                    px, py = geo.center((4, 4))
                    canvas.xview_moveto(max(0.0, (px-canvas.winfo_width()/2)/geo.width))
                    canvas.yview_moveto(max(0.0, (py-canvas.winfo_height()/2)/geo.height))
                    root.update()
                    buttons['Pipette sol'].invoke()
                    click(int(px-canvas.canvasx(0)), int(py-canvas.canvasy(0)))
                    self.assertEqual(brush.get(), 'surface:dirt')
                    save_as(root)
                    saved = json.loads(output.read_text(encoding='utf-8'))
                    tiles = {tuple(t['pos']): t
                             for t in saved['missions'][0]['board']['tiles']}
                    self.assertEqual(tiles[(4, 4)]['surface'], 'dirt')
                    self.assertEqual(tiles[(5, 4)]['surface'], 'dirt')
                    self.assertEqual(tiles.get((5, 5), {}).get('surface', 'grass'),
                                     'grass')
                    self.assertEqual(tiles[(6, 4)]['feature'], 'arch')
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(output)), \
                 patch('tkinter.messagebox.showerror') as dialog_error:
                launch(DEFAULT_CONTENT)
                dialog_error.assert_not_called()



    def test_multicell_structure_rotation_preview_undo_and_iso_save(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.authoring import add_blank_mission
        from sporebound.iso_map import IsoGeometry
        from sporebound.model import Content

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            source = Path(tmp) / 'structure_source.json'
            saved_path = Path(tmp) / 'structures_ui.json'
            mid = 'structure_ui'
            payload = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                        mid, 'Structure UI', 12, 12)
            source.write_text(json.dumps(payload), encoding='utf-8')
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *err: errors.append(err)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    mission = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                   and mid in w.cget('values'))
                    structure_box = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                         and 'Rempart' in w.cget('values'))
                    tool = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                and 'Structure' in w.cget('values'))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    mission.set(mid)
                    mission.event_generate('<<ComboboxSelected>>')
                    root.update()

                    def click(x, y):
                        canvas.event_generate('<Button-1>', x=x, y=y)
                        canvas.event_generate('<ButtonRelease-1>', x=x, y=y)
                        root.update()

                    structure_box.set('Maison')
                    buttons['↻ Bâtiment'].invoke()
                    self.assertEqual(tool.get(), 'Structure')
                    x, y = 3*54+12, 3*54+12
                    canvas.event_generate('<Motion>', x=x, y=y)
                    root.update()
                    preview = canvas.find_withtag('structure_preview')
                    self.assertEqual(len(preview), 12)
                    self.assertEqual(canvas.itemcget(preview[0], 'outline'),
                                     '#36a16c')
                    click(x, y)
                    save_as(root)
                    first = Content.load(saved_path).missions[mid].board
                    # A 4x3 maison is now a 3x4 rotated footprint.
                    self.assertTrue(first.tile((3, 3)).blocked)
                    self.assertFalse(first.tile((6, 4)).blocked)
                    buttons['Annuler'].invoke()
                    save_as(root)
                    undone = Content.load(saved_path).missions[mid].board
                    self.assertFalse(undone.tile((3, 3)).blocked)
                    buttons['Rétablir'].invoke()
                    save_as(root)
                    restored = Content.load(saved_path).missions[mid].board
                    self.assertTrue(restored.tile((3, 3)).blocked)

                    toggle = next(w for w in widgets if isinstance(w, ttk.Radiobutton)
                                  and w.cget('text') == 'Iso 2.5D')
                    toggle.invoke()
                    structure_box.set('Pont')
                    structure_box.event_generate('<<ComboboxSelected>>')
                    root.update()
                    geo = IsoGeometry(restored, 54)
                    px, py = geo.center((7, 7))
                    canvas.xview_moveto(max(0.0,
                        (px-canvas.winfo_width()/2)/geo.width))
                    canvas.yview_moveto(max(0.0,
                        (py-canvas.winfo_height()/2)/geo.height))
                    root.update()
                    x, y = int(px-canvas.canvasx(0)), int(py-canvas.canvasy(0))
                    self.assertTrue(0 <= x < canvas.winfo_width())
                    self.assertTrue(0 <= y < canvas.winfo_height())
                    canvas.event_generate('<Motion>', x=x, y=y)
                    root.update()
                    self.assertTrue(canvas.find_withtag('structure_preview'))
                    click(x, y)
                    save_as(root)
                    final = Content.load(saved_path).missions[mid].board
                    self.assertEqual(final.tile((7, 7)).surface, 'bridge')
                    self.assertEqual(final.tile((8, 9)).surface, 'bridge')
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with (patch.object(tk.Tk, 'mainloop', drive),
                  patch('tkinter.filedialog.asksaveasfilename',
                        return_value=str(saved_path)),
                  patch('tkinter.messagebox.showerror') as dialog_error):
                launch(source)
                dialog_error.assert_not_called()



    def test_roof_cutaway_and_door_pivot_after_save(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.authoring import add_blank_mission
        from sporebound.model import Content

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            source = Path(tmp) / 'architecture_source.json'
            saved = Path(tmp) / 'architecture_saved.json'
            mid = 'roof_gui'
            payload = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                        mid, 'Roof GUI', 12, 12)
            source.write_text(json.dumps(payload), encoding='utf-8')
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    comboboxes = [w for w in widgets if isinstance(w, ttk.Combobox)]
                    mission = next(w for w in comboboxes if mid in w.cget('values'))
                    tool = next(w for w in comboboxes
                                if 'Structure' in w.cget('values'))
                    pivot = next(w for w in comboboxes
                                 if 'Centre' in w.cget('values'))
                    door = next(w for w in comboboxes
                                if 'Entrée B' in w.cget('values'))
                    mission.set(mid)
                    mission.event_generate('<<ComboboxSelected>>')
                    root.update()
                    pivot.set('Centre')
                    door.set('Entrée B')
                    buttons['Poser structure'].invoke()
                    self.assertEqual(tool.get(), 'Structure')

                    def click(x, y):
                        canvas.event_generate('<Button-1>', x=x, y=y)
                        canvas.event_generate('<ButtonRelease-1>', x=x, y=y)
                        root.update()

                    click(4*54+12, 4*54+12)
                    save_as(root)
                    board = Content.load(saved).missions[mid].board
                    self.assertTrue(board.tile((3, 3)).blocked)
                    self.assertEqual(board.tile((5, 5)).surface, 'cobble')
                    toggle = next(w for w in widgets if isinstance(w, ttk.Radiobutton)
                                  and w.cget('text') == 'Iso 2.5D')
                    toggle.invoke()
                    root.update()
                    # The selected cell is inside the house: no opaque roof.
                    self.assertEqual(len(canvas.find_withtag('architecture_roof')), 0)
                    self.assertGreater(len(canvas.find_withtag('architecture_cutaway')), 0)
                    roofs = next(w for w in widgets if isinstance(w, ttk.Checkbutton)
                                 and w.cget('text') == 'Toitures')
                    roofs.invoke()
                    root.update()
                    self.assertEqual(len(canvas.find_withtag('architecture_cutaway')), 0)
                    roofs.invoke()
                    root.update()
                    self.assertGreater(len(canvas.find_withtag('architecture_cutaway')), 0)
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with (patch.object(tk.Tk, 'mainloop', drive),
                  patch('tkinter.filedialog.asksaveasfilename',
                        return_value=str(saved)),
                  patch('tkinter.messagebox.showerror') as dialog_error):
                launch(source)
                dialog_error.assert_not_called()



    def test_isometric_building_png_renders_and_cuts_away_after_selection(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.authoring import add_blank_mission
        from sporebound.iso_map import IsoGeometry
        from sporebound.iso_structures import place_structure
        from sporebound.model import Content

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            source = Path(tmp) / 'buildings_gui.json'
            mid = 'buildings_gui'
            payload = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                        mid, 'Architecture PNG', 12, 12)
            payload = place_structure(payload, mid, 'Maison', (3, 3))
            source.write_text(json.dumps(payload), encoding='utf-8')
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *err: errors.append(err)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    mission = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                   and mid in w.cget('values'))
                    tool = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                and 'Sélection' in w.cget('values'))
                    toggle = next(w for w in widgets if isinstance(w, ttk.Radiobutton)
                                  and w.cget('text') == 'Iso 2.5D')
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    mission.set(mid)
                    mission.event_generate('<<ComboboxSelected>>')
                    toggle.invoke()
                    root.update()
                    self.assertTrue(canvas.find_withtag('architecture_sprite'))
                    self.assertFalse(canvas.find_withtag('architecture_roof'))
                    buttons['+'].invoke()
                    root.update()
                    self.assertTrue(canvas.find_withtag('architecture_sprite'))

                    tool.set('Sélection')
                    board = Content.from_dict(payload).missions[mid].board
                    geo = IsoGeometry(board, 60)
                    px, py = geo.center((4, 4))
                    canvas.xview_moveto(max(0.0, (px-canvas.winfo_width()/2)/geo.width))
                    canvas.yview_moveto(max(0.0, (py-canvas.winfo_height()/2)/geo.height))
                    root.update()
                    x, y = int(px-canvas.canvasx(0)), int(py-canvas.canvasy(0))
                    self.assertTrue(0 <= x < canvas.winfo_width())
                    self.assertTrue(0 <= y < canvas.winfo_height())
                    canvas.event_generate('<Button-1>', x=x, y=y)
                    canvas.event_generate('<ButtonRelease-1>', x=x, y=y)
                    root.update()
                    self.assertFalse(canvas.find_withtag('architecture_sprite'))
                    self.assertTrue(canvas.find_withtag('architecture_cutaway'))
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with (patch.object(tk.Tk, 'mainloop', drive),
                  patch('tkinter.messagebox.showerror') as dialog_error):
                launch(source)
                dialog_error.assert_not_called()



    def test_fortification_png_renders_three_structures_and_safe_cutaway(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.authoring import add_blank_mission
        from sporebound.iso_map import IsoGeometry
        from sporebound.iso_structures import place_structure
        from sporebound.model import Content

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            source = Path(tmp)/'fortifications_gui.json'
            mid = 'fortifications_gui'
            doc = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                    mid, 'Fortifications', 12, 12)
            doc = place_structure(doc, mid, 'Rempart', (3, 3))
            doc = place_structure(doc, mid, 'Escalier', (5, 5))
            doc = place_structure(doc, mid, 'Pont', (7, 8))
            source.write_text(json.dumps(doc), encoding='utf-8')
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    children = list(descendants(root))
                    canvas = next(w for w in children if isinstance(w, tk.Canvas))
                    mission = next(w for w in children if isinstance(w, ttk.Combobox)
                                   and mid in w.cget('values'))
                    tool = next(w for w in children if isinstance(w, ttk.Combobox)
                                and 'Sélection' in w.cget('values'))
                    toggle = next(w for w in children if isinstance(w, ttk.Radiobutton)
                                  and w.cget('text') == 'Iso 2.5D')
                    mission.set(mid)
                    mission.event_generate('<<ComboboxSelected>>')
                    toggle.invoke()
                    root.update()
                    self.assertEqual(len(canvas.find_withtag('architecture_scenery_sprite')), 3)
                    board = Content.from_dict(doc).missions[mid].board
                    geo = IsoGeometry(board, 54)
                    cell = (8, 9)
                    px, py = geo.center(cell)
                    canvas.xview_moveto(max(0.0, (px-canvas.winfo_width()/2)/geo.width))
                    canvas.yview_moveto(max(0.0, (py-canvas.winfo_height()/2)/geo.height))
                    root.update()
                    x, y = int(px-canvas.canvasx(0)), int(py-canvas.canvasy(0))
                    self.assertTrue(0 <= x < canvas.winfo_width())
                    self.assertTrue(0 <= y < canvas.winfo_height())
                    tool.set('Sélection')
                    canvas.event_generate('<Button-1>', x=x, y=y)
                    canvas.event_generate('<ButtonRelease-1>', x=x, y=y)
                    root.update()
                    self.assertEqual(len(canvas.find_withtag('architecture_scenery_sprite')), 2)
                    self.assertTrue(canvas.find_withtag('selection'))
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with (patch.object(tk.Tk, 'mainloop', drive),
                  patch('tkinter.messagebox.showerror') as dialog_error):
                launch(source)
                dialog_error.assert_not_called()


if __name__ == '__main__':
    unittest.main()
