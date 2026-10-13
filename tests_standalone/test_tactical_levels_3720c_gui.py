"""Real Tk validation: same scene/Player projects a moving hero on N1."""
import os
import unittest

from sporebound.engine import Battle
from sporebound.iso_battle_view import IsoBattleCanvas
from sporebound.presentation import Camera, battle_frame
from examples.layered_house_3720c import create
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires a real Tk/Xvfb display')
class LayeredGameplayGUI(unittest.TestCase):
    def test_actor_height_scene_and_upper_floor_picking(self):
        import tkinter as tk

        source, mid = create()
        mission = next(m for m in source['missions'] if m['id'] == mid)
        player = next(u['id'] for u in mission['units'] if u['team'] == 'player')
        for actor in mission['units']:
            actor['speed'] = 1000 if actor['team'] == 'player' else 1
        battle = Battle(Content.from_dict(source), mid, seed=7,
                        battle_id='layered-gui')
        self.assertEqual(battle.active_id, player)
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root, width=1000, height=750)
            canvas.pack()
            root.update()
            renderer = IsoBattleCanvas(canvas)
            for zoom in (24, 54, 96):
                with self.subTest(zoom=zoom):
                    camera = Camera(zoom)
                    geo = renderer.draw(battle, battle_frame(battle), camera)
                    # Enemy starts upstairs, so its floor must already be visible.
                    self.assertTrue(canvas.find_withtag('architecture_floor_1'))
                    battle.execute({'kind': 'level_move', 'level': 1, 'cell': [4, 5]})
                    geo = renderer.draw(battle, battle_frame(battle), camera)
                    self.assertTrue(canvas.find_withtag('architecture_floor_1'))
                    x, y = geo.center((4, 5))
                    self.assertEqual(renderer.hit_test(
                        x+renderer.shift[0], y-3*geo.step+renderer.shift[1],
                        level=1), (4, 5))
                    # Rebuild a clean pre-move battle for each zoom.
                    battle = Battle(Content.from_dict(source), mid, seed=7,
                                    battle_id='layered-gui')
            renderer.dispose()
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
