"""Real Tk/Xvfb acceptance of tower cutaway, floors and Player picking."""
import os
import unittest

from examples.layered_tower_3720_gate import create
from sporebound.engine import Battle
from sporebound.interior_levels import floor_hit_test
from sporebound.iso_battle_view import IsoBattleCanvas
from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_map import render_isometric
from sporebound.model import Content
from sporebound.presentation import Camera, battle_frame


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires an actual Tk/Xvfb display')
class InteriorBuilderTowerGUI(unittest.TestCase):
    def test_map_editor_cutaway_and_upper_floor_picking(self):
        import tkinter as tk

        source, mid = create()
        mission = Content.from_dict(source).missions[mid]
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
                                'Décors': True, 'Bâtiments': True,
                                'Toitures': True, 'Intérieurs': True,
                                'Étage actif': 1},
                        selected_cell=(0, 0), selected_tiles=(),
                        building_atlas=atlas)
                    self.assertFalse(canvas.find_withtag('architecture_sprite'))
                    self.assertTrue(canvas.find_withtag('architecture_floor_1'))
                    self.assertEqual(len(geo.architecture_instances), 1)
                    cx, cy = geo.center((4, 5))
                    floor = mission.interior_floors[0]
                    self.assertEqual(floor_hit_test(
                        geo, geo.architecture_instances[0], floor,
                        cx, cy - 3 * geo.step), (4, 5))
                    # Aim inside the exposed front half, not on a raised-wall edge.
                    self.assertEqual(geo.hit_test(cx, cy + geo.half_height * .5), (4, 5))
        finally:
            root.destroy()

    def test_player_actor_moves_into_visible_upper_tower(self):
        import tkinter as tk

        source, mid = create()
        content = Content.from_dict(source)
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root, width=1000, height=750)
            canvas.pack()
            root.update()
            renderer = IsoBattleCanvas(canvas)
            for zoom in (24, 54, 96):
                with self.subTest(zoom=zoom):
                    battle = Battle(content, mid, seed=7, battle_id='tower-gui')
                    camera = Camera(zoom)
                    renderer.draw(battle, battle_frame(battle), camera)
                    battle.execute({'kind': 'level_move', 'level': 1,
                                    'cell': [4, 5]})
                    geo = renderer.draw(battle, battle_frame(battle), camera)
                    self.assertTrue(canvas.find_withtag('architecture_floor_1'))
                    self.assertEqual(battle.unit_levels[battle.active_id], 1)
                    x, y = geo.center((4, 5))
                    self.assertEqual(renderer.hit_test(
                        x + renderer.shift[0],
                        y - 3 * geo.step + renderer.shift[1], level=1),
                        (4, 5))
            renderer.dispose()
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
