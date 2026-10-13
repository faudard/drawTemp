"""3.7.20B — real Tk visual proof for raised decks, selection and holes."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.interior_levels import (
    add_interior_floor, edit_interior_tile, floor_hit_test)
from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_map import render_isometric
from sporebound.iso_structures import place_structure
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Needs real Tk/Xvfb display')
class StackedInteriorsGUI(unittest.TestCase):
    def test_two_stacked_floors_and_upper_cell_picking(self):
        import tkinter as tk

        content = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                    'stacked_gui', 'Maison multi-niveaux', 16, 16)
        content = place_structure(content, 'stacked_gui', 'Maison', (3, 3))
        sid = next(m for m in content['missions'] if m['id'] == 'stacked_gui')['structures'][0]['id']
        content = add_interior_floor(content, 'stacked_gui', sid, 1)
        content = add_interior_floor(content, 'stacked_gui', sid, 2)
        content = edit_interior_tile(content, 'stacked_gui', sid, 2,
                                     (4, 4), feature='crate')
        mission = Content.from_dict(content).missions['stacked_gui']
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root, width=950, height=740)
            canvas.pack()
            root.update()
            atlas = IsoBuildingAtlas(canvas)
            for size in (24, 54, 96):
                with self.subTest(size=size):
                    geo = render_isometric(
                        canvas, mission.board, mission, mission.units,
                        cell_size=size,
                        layers={'Terrain': True, 'Relief': True,
                                'Bâtiments': True, 'Toitures': True,
                                'Intérieurs': True, 'Étage actif': 2},
                        selected_cell=(0, 0), selected_tiles=(),
                        building_atlas=atlas)
                    self.assertFalse(canvas.find_withtag('architecture_sprite'))
                    self.assertTrue(canvas.find_withtag('architecture_floor_1'))
                    self.assertTrue(canvas.find_withtag('architecture_floor_2'))
                    self.assertEqual(len(geo.architecture_instances), 1)
                    cx, cy = geo.center((4, 4))
                    level2 = mission.interior_floors[1]
                    self.assertEqual(floor_hit_test(
                        geo, geo.architecture_instances[0], level2,
                        cx, cy - 6 * geo.step), (4, 4))
                    self.assertEqual(geo.hit_test(cx, cy), (4, 4))
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
