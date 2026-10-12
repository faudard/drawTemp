"""3.7.18B cosmetic isometric motion and per-building depth occlusion."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_architecture import (
    architecture_instances, draw_architecture, roof_cutaway)
from sporebound.iso_depth import (
    actor_depth, architecture_depth, cutaway_intersects, depth_order,
    visual_center, visual_height, visual_position)
from sporebound.iso_map import IsoGeometry, render_isometric
from sporebound.iso_structures import place_structure
from sporebound.model import Content
from sporebound.visual_motion import ActorPose, MotionDirector
from sporebound.presentation import ActorView, BattleFrame, TileView


def unit(uid, x, y, *, alive=True, height=1, width=1):
    return SimpleNamespace(id=uid, name=uid, team='player',
                           pos=(x, y), footprint=(width, height),
                           alive=alive, hp=32)


class CanvasEvidence:
    def __init__(self):
        self.items = []
        self.raised = []

    def __getattr__(self, name):
        if name == 'tag_raise':
            def raised(tag, *args):
                self.raised.append(tag)
            return raised
        if name.startswith(('create_', 'delete', 'configure')):
            def record(*args, **kw):
                self.items.append((name, args, kw))
                return len(self.items)
            return record
        raise AttributeError(name)

    def tagged(self, value, kind=None):
        return [(method, args, kw) for method, args, kw in self.items
                if value in kw.get('tags', ()) and (kind is None or kind == method)]


class SpriteStub:
    def sprite(self, *args):
        return object()


class IsoMotionAndDepthTests(unittest.TestCase):
    def setUp(self):
        source = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                   'iso_depth_test', 'Depth', 12, 12)
        self.mission_id = 'iso_depth_test'
        self.doc = Document(Content.from_dict(source))
        self.doc.replace(place_structure(self.doc.data, self.mission_id,
                                         'Maison', (3, 3)))

    def get_scene(self):
        mission = Content.from_dict(self.doc.data).missions[self.mission_id]
        return mission, mission.board, architecture_instances(mission.board)[0]

    def test_bilinear_elevation_and_fractional_isometric_projection(self):
        mission, board, _ = self.get_scene()
        geo = IsoGeometry(board, 54)
        actor = unit('runner', 1, 1)
        self.assertEqual(visual_center(geo, actor), geo.center((1, 1)))
        pose = {'runner': ActorPose(2.5, 1.0, 'move', 'east')}
        point = visual_center(geo, actor, pose)
        self.assertAlmostEqual(point[0], geo.origin_x+1.5*geo.half_width)
        self.assertAlmostEqual(point[1], geo.origin_y+3.5*geo.half_height
                               -visual_height(board, (2.5, 1))*geo.step)
        self.assertEqual(visual_position(actor, pose), (2.5, 1.0))
        self.assertEqual(actor.pos, (1, 1))  # visual state never mutates actor
        self.assertEqual(visual_height(board, (3, 3)), board.tile((3, 3)).height)
        self.assertAlmostEqual(visual_height(board, (2.5, 3)),
                               (board.tile((2, 3)).height +
                                board.tile((3, 3)).height)/2)

    def test_depth_order_puts_rear_actor_behind_facade_and_front_actor_ahead(self):
        mission, board, house = self.get_scene()
        rear, near = unit('rear', 0, 1), unit('near', 9, 9)
        self.assertLess(actor_depth(rear), architecture_depth(house))
        self.assertGreater(actor_depth(near), architecture_depth(house))
        self.assertEqual(depth_order((house,), (rear, near)),
                         ('iso_actor_unit_0', 'architecture_instance_0',
                          'iso_actor_unit_1'))
        rear_pose = {'rear': ActorPose(10., 8., 'move', 'east')}
        self.assertEqual(depth_order((house,), (rear, near), rear_pose),
                         ('architecture_instance_0', 'iso_actor_unit_1',
                          'iso_actor_unit_0'))
        # Stable ordering for exact ties; architecture wins, foreground actor
        # still raised later, never relying on arbitrary dict iteration.
        self.assertEqual(depth_order((house,), (rear, near)),
                         depth_order((house,), (rear, near)))

    def test_roof_cutaway_transitions_at_door_and_does_not_modify_tiles(self):
        mission, board, house = self.get_scene()
        state = deepcopy(self.doc.data)
        entering = unit('entering', 2, 4)
        self.assertFalse(roof_cutaway(house, (0, 0), (entering,)))
        self.assertFalse(cutaway_intersects(house, entering))
        transit = {'entering': ActorPose(2.25, 4., 'move', 'east')}
        self.assertTrue(cutaway_intersects(house, entering, transit))
        self.assertTrue(roof_cutaway(house, (0, 0), (entering,), transit))
        hidden = unit('hidden', 4, 4, alive=False)
        self.assertFalse(roof_cutaway(house, (0, 0), (hidden,)))
        self.assertTrue(roof_cutaway(house, (4, 4), ()))
        self.assertEqual(self.doc.data, state)

    def test_render_reorders_actor_groups_and_interpolates_pixel_position(self):
        mission, board, house = self.get_scene()
        actors = (unit('back', 0, 1), unit('front', 9, 9))
        poses = {'front': ActorPose(8.5, 8.0, 'move', 'north')}
        geo = IsoGeometry(board, 54)
        canvas = CanvasEvidence()
        render_isometric(
            canvas, board, mission, actors, cell_size=54,
            layers={'Terrain': True, 'Relief': True, 'Bâtiments': True,
                    'Toitures': True, 'Unités': True},
            selected_cell=(0, 0), selected_tiles=(),
            building_atlas=SpriteStub(), poses=poses)
        self.assertTrue(canvas.tagged('architecture_instance_0', 'create_image'))
        self.assertEqual(canvas.raised[-4:],
                         ['iso_actor_unit_0', 'architecture_instance_0',
                          'iso_actor_unit_1', 'selection'])
        oval = canvas.tagged('iso_actor_unit_1', 'create_oval')[0]
        point = visual_center(geo, actors[1], poses)
        self.assertAlmostEqual((oval[1][0]+oval[1][2])/2, point[0])
        self.assertAlmostEqual((oval[1][1]+oval[1][3])/2, point[1])
        self.assertEqual(actors[1].pos, (9, 9))

    def test_authoritative_motion_director_is_reused_without_advancing_battle(self):
        actor_a = ActorView('hero', 'Hero', 'player', (1, 1), (1, 1),
                            30, 30, 0, 0, True, True, ())
        actor_b = ActorView('hero', 'Hero', 'player', (3, 1), (1, 1),
                            30, 30, 0, 0, True, True, ())
        baseline = BattleFrame('mission', 8, 8, 0, 'hero', False, None,
                               (TileView((1, 1), 0, False, 0, 0),),
                               (actor_a,), (), (1, 1), (), (), ())
        moved = __import__('dataclasses').replace(baseline, actors=(actor_b,))
        motion = MotionDirector(duration_ms=280)
        motion.observe(baseline, 1000)
        motion.observe(moved, 1100)
        mid = motion.poses(1240)['hero']
        self.assertEqual((mid.x, mid.y), (2, 1))
        self.assertEqual(mid.action, 'move')
        self.assertTrue(motion.active(1240))
        self.assertEqual(motion.poses(1380)['hero'].x, 3)
        self.assertFalse(motion.active(1380))
        self.assertEqual(moved.actors[0].pos, (3, 1))


if __name__ == '__main__':
    unittest.main()
