"""3.7.18B real Tk proof: compositing behind/front of house and moving feet."""
import os
from types import SimpleNamespace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_depth import visual_center
from sporebound.iso_map import IsoGeometry, render_isometric
from sporebound.iso_structures import place_structure
from sporebound.model import Content
from sporebound.visual_motion import ActorPose


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Needs a real Tk/Xvfb screen')
class IsoMotionOcclusionGuiTests(unittest.TestCase):
    def test_house_occludes_rear_unit_not_front_and_cuts_on_doorway(self):
        import tkinter as tk
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root, width=940, height=750)
            canvas.pack()
            root.update()
            source = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                       'depth_gui', 'House', 12, 12)
            source = place_structure(source, 'depth_gui', 'Maison', (3, 3))
            mission = Content.from_dict(source).missions['depth_gui']
            board = mission.board
            atlas = IsoBuildingAtlas(canvas)
            rear = SimpleNamespace(id='rear',name='rear',team='player',
                                   pos=(1, 1), footprint=(1, 1),
                                   hp=30,alive=True)
            front = SimpleNamespace(id='front',name='front',team='enemy',
                                    pos=(9, 9), footprint=(1, 1),
                                    hp=25,alive=True)
            def draw(actors, poses=None):
                return render_isometric(
                    canvas, board, mission, actors, cell_size=54,
                    layers={'Terrain': True,'Relief': True,'Décors': True,
                            'Bâtiments': True,'Toitures': True,'Unités': True},
                    selected_cell=(0, 0),selected_tiles=(),
                    building_atlas=atlas, poses=poses)
            geo = draw((rear, front))
            rear_items = canvas.find_withtag('iso_actor_unit_0')
            house_items = canvas.find_withtag('architecture_instance_0')
            front_items = canvas.find_withtag('iso_actor_unit_1')
            self.assertTrue(rear_items and front_items and house_items)
            self.assertTrue(canvas.find_withtag('architecture_sprite'))
            order = canvas.find_all()
            depths = {item: i for i, item in enumerate(order)}
            self.assertLess(max(depths[i] for i in rear_items),
                            min(depths[i] for i in house_items))
            self.assertLess(max(depths[i] for i in house_items),
                            min(depths[i] for i in front_items))

            poses = {'front':ActorPose(8.5, 8., 'move','north')}
            geo = draw((rear, front), poses)
            front_oval = next(i for i in canvas.find_withtag('iso_actor_unit_1')
                              if canvas.type(i) == 'oval')
            x1,y1,x2,y2 = canvas.coords(front_oval)
            expected = visual_center(geo, front, poses)
            self.assertAlmostEqual((x1+x2)/2, expected[0], delta=1)
            self.assertAlmostEqual((y1+y2)/2, expected[1]-14.5, delta=1)
            self.assertTrue(canvas.find_withtag('architecture_sprite'))

            entrant = SimpleNamespace(id='entrant', name='entrant',
                                      team='player', pos=(2, 4),
                                      footprint=(1, 1),hp=22,alive=True)
            draw((entrant,), {'entrant':ActorPose(2.4, 4., 'move','east')})
            self.assertFalse(canvas.find_withtag('architecture_sprite'))
            self.assertTrue(canvas.find_withtag('architecture_cutaway'))
            self.assertEqual(entrant.pos, (2, 4))
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
