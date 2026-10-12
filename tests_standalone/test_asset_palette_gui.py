"""Actual palette → iso placement → undo/redo → disk → playtest, under Tk/Xvfb."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import launch
from sporebound.iso_map import IsoGeometry, IsoTerrainAtlas
from sporebound.iso_props import IsoPropAtlas
from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_fortification_atlas import IsoFortificationAtlas
from sporebound.model import Content
from sporebound.studio_asset_palette import AssetPalette


def descendants(parent):
    for child in parent.winfo_children():
        yield child
        yield from descendants(child)


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1', 'Requires Tk display')
class AssetPaletteGUITests(unittest.TestCase):
    def test_real_catalog_png_cache_missing_invalid_and_empty_search(self):
        import tkinter as tk
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root)
            selected = []
            with TemporaryDirectory() as tmp:
                invalid = Path(tmp)/'invalid.png'
                invalid.write_bytes(b'not a png')
                palette = AssetPalette(root, terrain=IsoTerrainAtlas(canvas),
                    props=IsoPropAtlas(canvas, path=Path(tmp)/'absent.png'),
                    buildings=IsoBuildingAtlas(canvas, path=invalid),
                    fortifications=IsoFortificationAtlas(canvas),
                    choose=lambda e, t: selected.append((e.id, t)) or True,
                    cell_size=lambda: 54)
                root.update()
                for identifier, text in [('feature:tree', 'PNG absent'),
                                         ('structure:Maison', 'PNG invalide')]:
                    palette.tree.selection_set(identifier)
                    palette.select()
                    self.assertIn(text, palette.detail.get())
                    self.assertFalse(palette.use_button.instate(['disabled']))
                palette.tree.selection_set('structure:Pont')
                palette.select()
                for scale in (24, 54, 96):
                    palette.scale.set(scale)
                    palette.preview()
                    self.assertEqual(palette.preview_image.width(), round(450*scale/36))
                    image = palette.preview_image
                    palette.preview()
                    self.assertIs(image, palette.preview_image)
                palette.rotate()
                self.assertIn('90°', palette.detail.get())
                palette.use()
                self.assertEqual(selected, [('structure:Pont', 1)])
                palette.show()
                palette.query.set('nothing matches')
                root.update()
                self.assertFalse(palette.tree.get_children())
                self.assertTrue(palette.use_button.instate(['disabled']))
                palette.use()
                self.assertEqual(len(selected), 1)
        finally:
            root.destroy()

    def test_all_iso_loaders_keep_lower_right_frame_pixels_at_palette_and_map_scales(self):
        import tkinter as tk
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root)
            cases = (
                (IsoTerrainAtlas(canvas), (96, 48), 4, 16, 'stone', False),
                (IsoPropAtlas(canvas), (96, 128), 2, 12, 'boulder', False),
                (IsoBuildingAtlas(canvas), (350, 220), 2, 6, 'Tour', True),
                (IsoFortificationAtlas(canvas), (450, 250), 2, 6, 'Escalier', True))
            for loader, (fw, fh), index, count, name, structure in cases:
                source = tk.PhotoImage(master=canvas, width=fw*count, height=fh)
                x = index*fw
                source.put('#ff00aa', to=(x+int(fw*.6), int(fh*.6),
                                         x+int(fw*.95), int(fh*.95)))
                loader._source = source
                for size in (8, 22, 24, 54, 96):
                    with self.subTest(loader=type(loader).__name__, size=size):
                        photo = (loader.tile(name, size) if hasattr(loader, 'tile')
                                 else loader.sprite(name, 0, size) if structure
                                 else loader.sprite(name, size))
                        self.assertIsNotNone(photo)
                        self.assertEqual(photo.get(int(photo.width()*.75),
                                                   int(photo.height()*.75)),
                                         (255, 0, 170))
                        self.assertTrue(photo.transparency_get(1, 1))
        finally:
            root.destroy()

    def test_editor_palette_scene_save_reload_undo_and_playtest_guard(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.iso_architecture import architecture_instances
        with TemporaryDirectory() as tmp:
            source, target = Path(tmp)/'source.json', Path(tmp)/'scene.json'
            data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                     'palette', 'Scène médiévale', 16, 16)
            # Authoring fixture only; actual scene is painted through GUI below.
            data['missions'].sort(key=lambda m: m['id'] != 'palette')
            source.write_text(json.dumps(data), encoding='utf-8')
            errors, palettes = [], []
            original_init = AssetPalette.__init__

            def capture(instance, *args, **kwargs):
                original_init(instance, *args, **kwargs)
                palettes.append(instance)

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    buttons = {w.cget('text'): w for w in widgets if isinstance(w, ttk.Button)}
                    buttons['Bibliothèque d’assets'].invoke()
                    root.update()
                    palette = palettes[0]
                    board = Content.from_dict(data).missions['palette'].board
                    geo = IsoGeometry(board, 54)

                    def paint(identifier, cell, turns=0):
                        palette.show()
                        palette.query.set('')
                        palette.category.set('Tous')
                        root.update()
                        palette.tree.selection_set(identifier)
                        root.update()
                        for _ in range(turns):
                            palette.rotate_button.invoke()
                        palette.use_button.invoke()
                        root.update()
                        px, py = geo.center(cell)
                        canvas.xview_moveto(max(0, (px-canvas.winfo_width()/2)/geo.width))
                        canvas.yview_moveto(max(0, (py-canvas.winfo_height()/2)/geo.height))
                        root.update()
                        x, y = int(px-canvas.canvasx(0)), int(py-canvas.canvasy(0))
                        self.assertTrue(0 <= x < canvas.winfo_width())
                        self.assertTrue(0 <= y < canvas.winfo_height())
                        canvas.event_generate('<Button-1>', x=x, y=y)
                        canvas.event_generate('<ButtonRelease-1>', x=x, y=y)
                        root.update()

                    paint('surface:cobble', (2, 2))
                    paint('surface:water', (2, 4))
                    paint('feature:tree', (3, 2))
                    paint('structure:Pont', (6, 6), turns=1)
                    buttons['Enregistrer sous'].invoke()
                    first = Content.load(target)
                    board = first.missions['palette'].board
                    self.assertEqual(board.tile((2, 2)).surface, 'cobble')
                    self.assertTrue(board.tile((2, 4)).blocked)
                    self.assertEqual(board.tile((3, 2)).feature, 'tree')
                    bridge = next(b for b in architecture_instances(board) if b.name == 'Pont')
                    self.assertEqual((bridge.width, bridge.height), (2, 3))
                    buttons['Annuler'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertFalse(architecture_instances(Content.load(target).missions['palette'].board))
                    buttons['Rétablir'].invoke()
                    paint('structure:Maison', (9, 9))
                    paint('structure:Rempart', (3, 11))
                    buttons['Enregistrer sous'].invoke()
                    saved = Content.load(target)
                    self.assertEqual({b.name for b in architecture_instances(saved.missions['palette'].board)},
                                     {'Maison', 'Pont', 'Rempart'})
                    # Actual reopen path, not only a decoder assertion.
                    buttons['Ouvrir'].invoke()
                    root.update()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(Content.load(target).to_dict(), saved.to_dict())
                    buttons['Playtest'].invoke()
                    palette.show()
                    root.update()
                    self.assertFalse(palette.choose(palette.entries['feature:tree'], 0))
                    buttons['Éditer'].invoke()
                    root.update()
                    self.assertTrue(palette.choose(palette.entries['feature:tree'], 0))
                    self.assertEqual(errors, [])
                    # Optional visual proof from this actual tested editor, no runtime dependency.
                    evidence = os.environ.get('SPOREBOUND_PALETTE_SCREENSHOT')
                    if evidence:
                        from PIL import ImageGrab
                        palette.show()
                        palette.category.set('Structures')
                        palette.tree.selection_set('structure:Maison')
                        palette.scale.set(24)
                        root.update()
                        palette.window.geometry('860x660+560+310')
                        root.update()
                        ImageGrab.grab(xdisplay=os.environ.get('DISPLAY')).save(evidence)
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch.object(AssetPalette, '__init__', capture), \
                 patch('tkinter.filedialog.asksaveasfilename', return_value=str(target)), \
                 patch('tkinter.filedialog.askopenfilename', return_value=str(target)), \
                 patch('tkinter.messagebox.showerror') as error:
                launch(source)
                error.assert_not_called()
