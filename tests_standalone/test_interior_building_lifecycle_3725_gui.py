"""Tk smoke: a moved two-deck house stays visible and independently pickable."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.interior_levels import (
    add_interior_floor, floor_hit_test)
from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_map import render_isometric
from sporebound.iso_structures import move_structure, place_structure
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires a real Tk/Xvfb display')
class MovedStackedInteriorGUI(unittest.TestCase):
    def test_two_decks_after_move_and_roof_reinstatement_at_three_zooms(self):
        import tkinter as tk

        mid = 'moved_stacked_gui'
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 mid, 'Maison déplacée', 18, 18)
        data = place_structure(data, mid, 'Maison', (3, 3))
        sid = next(m for m in data['missions'] if m['id'] == mid)['structures'][0]['id']
        data = add_interior_floor(data, mid, sid, 1)
        data = add_interior_floor(data, mid, sid, 2)
        data = move_structure(data, mid, (4, 4), (6, 3))
        mission = Content.from_dict(data).missions[mid]
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root, width=1000, height=750)
            canvas.pack()
            root.update()
            atlas = IsoBuildingAtlas(canvas)
            for zoom in (24, 54, 96):
                with self.subTest(zoom=zoom):
                    geo = render_isometric(
                        canvas, mission.board, mission, mission.units,
                        cell_size=zoom,
                        layers={'Terrain': True, 'Relief': True,
                                'Bâtiments': True, 'Toitures': True,
                                'Intérieurs': True, 'Étage actif': 2},
                        selected_cell=(0, 0), selected_tiles=(),
                        building_atlas=atlas)
                    self.assertFalse(canvas.find_withtag('architecture_sprite'))
                    for level in (1, 2):
                        self.assertTrue(canvas.find_withtag(
                            'architecture_floor_' + str(level)))
                        cx, cy = geo.center((7, 5))
                        floor = next(f for f in mission.interior_floors
                                     if f['level'] == level)
                        self.assertEqual(floor_hit_test(
                            geo, geo.architecture_instances[0], floor,
                            cx, cy - level * 3 * geo.step), (7, 5))
                    render_isometric(
                        canvas, mission.board, mission, mission.units,
                        cell_size=zoom,
                        layers={'Terrain': True, 'Relief': True,
                                'Bâtiments': True, 'Toitures': True,
                                'Intérieurs': False, 'Étage actif': 0},
                        selected_cell=(0, 0), selected_tiles=(),
                        building_atlas=atlas)
                    self.assertTrue(canvas.find_withtag('architecture_sprite'))
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
