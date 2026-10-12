"""3.7.18C Tk/Xvfb: static Canvas item IDs survive actor motion frames."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.iso_battle_view import IsoBattleCanvas
from sporebound.model import Content
from sporebound.presentation import Camera, battle_frame
from sporebound.visual_motion import ActorPose


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk with a display')
class IsoFrameCacheGuiTests(unittest.TestCase):
    def test_real_tk_retains_static_canvas_items_and_updates_actor_pose(self):
        import tkinter as tk
        root = tk.Tk()
        try:
            root.geometry('880x650')
            canvas = tk.Canvas(root, width=820, height=540)
            canvas.pack()
            root.update()
            battle = Battle(Content.load(DEFAULT_CONTENT), 'garden', seed=13)
            frame = battle_frame(battle, (2, 2))
            camera = Camera(54, 0, 0)
            renderer = IsoBattleCanvas(canvas)
            actor = battle.units[0]
            renderer.draw(battle, frame, camera)
            self.assertEqual(renderer._scene_rebuilds, 1)
            all_ids = canvas.find_all()
            self.assertTrue(all_ids)
            first_actor_items = canvas.find_withtag('iso_actor_unit_0')
            self.assertTrue(first_actor_items)
            first_coords = canvas.coords(first_actor_items[0])
            terrain_ids = set(all_ids) - set(canvas.find_withtag('iso_actor'))
            x, y = actor.pos
            for tick in range(1, 9):
                renderer.draw(battle, frame, camera,
                              poses={actor.id: ActorPose(
                                  x+tick*.08, y, 'move', 'east')})
                self.assertEqual(canvas.find_withtag('iso_actor_unit_0'),
                                 first_actor_items)
                self.assertTrue(terrain_ids.issubset(canvas.find_all()))
            self.assertNotEqual(canvas.coords(first_actor_items[0]),
                                first_coords)
            self.assertEqual(renderer._scene_rebuilds, 1)
            self.assertEqual(renderer._actor_only_frames, 8)
            # Zoom invalidates static items and projects them at the new size.
            renderer.draw(battle, frame, Camera(62, 0, 0))
            self.assertEqual(renderer._scene_rebuilds, 2)
            # A tactical selection must not leave stale outlines.
            new_frame = battle_frame(battle, (3, 3))
            renderer.draw(battle, new_frame, Camera(62, 0, 0))
            self.assertEqual(renderer._scene_rebuilds, 3)
            self.assertTrue(canvas.find_withtag('selection'))
            renderer.dispose()
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
