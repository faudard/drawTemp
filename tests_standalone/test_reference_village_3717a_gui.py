"""Tk/Xvfb visual gate of the same authored village at three real zooms."""
import os
from pathlib import Path
import unittest

from examples.fortified_village_3717a import MISSION_ID, build_village_document
from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_fortification_atlas import IsoFortificationAtlas
from sporebound.iso_map import IsoTerrainAtlas, render_isometric
from sporebound.iso_props import IsoPropAtlas
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Needs a real Tk/Xvfb display')
class ReferenceVillageGUITests(unittest.TestCase):
    def test_real_atlases_render_village_and_preserve_picking_at_three_scales(self):
        import tkinter as tk
        doc = build_village_document(Content.load(DEFAULT_CONTENT))
        mission = Content.from_dict(doc.data).missions[MISSION_ID]
        root = tk.Tk()
        root.title('3.7.17A — Le Pont de Valcroix — Isometric evidence')
        root.geometry('1200x820+0+0')
        canvas = tk.Canvas(root, bg='#e4dfd5', highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        terrain = IsoTerrainAtlas(canvas)
        props = IsoPropAtlas(canvas)
        buildings = IsoBuildingAtlas(canvas)
        fortifications = IsoFortificationAtlas(canvas)
        output = os.environ.get('SPOREBOUND_VILLAGE_SCREENSHOT_DIR')
        try:
            root.update()
            for cell_size in (24, 54, 96):
                with self.subTest(zoom=cell_size):
                    geo = render_isometric(
                        canvas, mission.board, mission, mission.units,
                        cell_size=cell_size,
                        layers={name: True for name in
                                ('Terrain', 'Relief', 'Décors', 'Bâtiments',
                                 'Toitures', 'Objets', 'Unités', 'Objectifs')},
                        selected_cell=(15, 9), selected_tiles=(),
                        atlas=terrain, prop_atlas=props,
                        building_atlas=buildings,
                        fortification_atlas=fortifications)
                    self.assertEqual(geo.hit_test(*geo.center((13, 9))), (13, 9))
                    self.assertEqual(geo.hit_test(*geo.center((23, 9))), (23, 9))
                    self.assertGreaterEqual(len(canvas.find_withtag('architecture')), 8)
                    self.assertGreater(len(canvas.find_withtag('decor_sprite')), 5)
                    self.assertGreater(len(canvas.find_withtag('iso_actor')), 0)
                    self.assertIsNotNone(terrain._source)
                    self.assertIsNotNone(props._source)
                    self.assertIsNotNone(buildings._source)
                    self.assertIsNotNone(fortifications._source)
                    root.update()
                    center_x, center_y = geo.center((13, 9))
                    width, height = canvas.winfo_width(), canvas.winfo_height()
                    canvas.xview_moveto(max(0.0, (center_x-width/2)/geo.width))
                    canvas.yview_moveto(max(0.0, (center_y-height/2)/geo.height))
                    root.update()
                    if output:
                        from PIL import ImageGrab
                        dest = Path(output)
                        dest.mkdir(parents=True, exist_ok=True)
                        x, y = root.winfo_rootx(), root.winfo_rooty()
                        ImageGrab.grab(bbox=(x, y, x+root.winfo_width(),
                                             y+root.winfo_height()),
                                       xdisplay=os.environ.get('DISPLAY')).save(
                                           dest / f'village-{cell_size}.png')
        finally:
            root.destroy()


    def test_valcroix_bridge_restoration_stays_visible_across_zoom_levels(self):
        """Real ISO renderer: bridge translation and exposed river at 24/54/96."""
        import tkinter as tk
        from sporebound.iso_architecture import architecture_instances
        from sporebound.iso_structures import move_structure, remove_structure

        doc = build_village_document(Content.load(DEFAULT_CONTENT))
        states = []
        states.append(('before', Content.from_dict(doc.data).missions[MISSION_ID]))
        doc.replace(move_structure(doc.data, MISSION_ID, (13, 9), (12, 7)))
        states.append(('moved', Content.from_dict(doc.data).missions[MISSION_ID]))
        doc.replace(remove_structure(doc.data, MISSION_ID, (13, 7)))
        states.append(('restored', Content.from_dict(doc.data).missions[MISSION_ID]))
        self.assertEqual([len(architecture_instances(m.board, m.structures))
                          for _, m in states], [10, 10, 9])
        self.assertEqual(states[-1][1].board.tile((13, 9)).surface, 'water')
        self.assertEqual(states[-1][1].board.tile((13, 7)).surface, 'water')

        root = tk.Tk()
        root.title('Valcroix — structure underlay / visual regression')
        root.geometry('1200x820+0+0')
        canvas = tk.Canvas(root, bg='#e4dfd5', highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        terrain = IsoTerrainAtlas(canvas)
        props = IsoPropAtlas(canvas)
        buildings = IsoBuildingAtlas(canvas)
        fortifications = IsoFortificationAtlas(canvas)
        output = os.environ.get('SPOREBOUND_VILLAGE_SCREENSHOT_DIR')
        try:
            root.update()
            for label, mission in states:
                for zoom in (24, 54, 96):
                    with self.subTest(stage=label, zoom=zoom):
                        geo = render_isometric(
                            canvas, mission.board, mission, mission.units,
                            cell_size=zoom,
                            layers={name: True for name in
                                    ('Terrain', 'Relief', 'Décors', 'Bâtiments',
                                     'Toitures', 'Objets', 'Unités', 'Objectifs')},
                            selected_cell=(0, 0), selected_tiles=(),
                            atlas=terrain, prop_atlas=props,
                            building_atlas=buildings,
                            fortification_atlas=fortifications)
                        self.assertEqual(
                            geo.hit_test(*geo.center((13, 9))), (13, 9))
                        self.assertGreaterEqual(
                            len(canvas.find_withtag('architecture')),
                            7 if label == 'restored' else 8)
                        self.assertIsNotNone(terrain._source)
                        self.assertIsNotNone(buildings._source)
                        self.assertIsNotNone(fortifications._source)
                        root.update()
                        if output:
                            # Artifacts preserve the *actual* Tk rendering;
                            # presence of a PNG is not an aesthetic sign-off.
                            cx, cy = geo.center((13, 9))
                            canvas.xview_moveto(max(
                                0., (cx - canvas.winfo_width()/2)/geo.width))
                            canvas.yview_moveto(max(
                                0., (cy - canvas.winfo_height()/2)/geo.height))
                            root.update()
                            from PIL import ImageGrab
                            dest = Path(output)
                            dest.mkdir(parents=True, exist_ok=True)
                            x, y = root.winfo_rootx(), root.winfo_rooty()
                            ImageGrab.grab(
                                bbox=(x, y, x + root.winfo_width(),
                                      y + root.winfo_height()),
                                xdisplay=os.environ.get('DISPLAY')).save(
                                    dest / f'village-underlay-{label}-{zoom}.png')
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
