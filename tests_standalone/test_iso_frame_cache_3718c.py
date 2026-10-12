"""3.7.18C: retain static isometric layers during clock-driven actor motion."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.engine import Battle
from sporebound.iso_architecture import architecture_instances
from sporebound.iso_battle_view import IsoBattleCanvas
from sporebound.model import Content
from sporebound.presentation import Camera, battle_frame
from sporebound.iso_structures import place_structure
from sporebound.visual_motion import ActorPose


class RecordedCanvas:
    def __init__(self, width=720, height=500):
        self.width = width
        self.height = height
        self.calls = []

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def __getattr__(self, method):
        if method.startswith(('create_', 'tag_', 'delete', 'move', 'configure')):
            def collect(*args, **kwargs):
                self.calls.append((method, args, kwargs))
                return len(self.calls)
            return collect
        raise AttributeError(method)

    def count(self, method, tag=None):
        return sum(name == method and
                   (tag is None or tag in kw.get('tags', ()))
                   for name, args, kw in self.calls)


class IsoFrameCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)

    def make_renderer(self):
        canvas = RecordedCanvas()
        renderer = IsoBattleCanvas(canvas)
        for atlas in (renderer.terrain, renderer.props, renderer.buildings,
                      renderer.fortifications):
            atlas._unavailable = True
        return canvas, renderer

    def test_motion_only_updates_actor_items_not_terrain_or_roofs(self):
        battle = Battle(self.content, 'garden', seed=11)
        before = battle.digest()
        frame = battle_frame(battle, (2, 2))
        camera = Camera(54, 0, 0)
        canvas, renderer = self.make_renderer()
        actors = tuple(battle.units)
        subject = actors[0]
        x, y = subject.pos
        renderer.draw(battle, frame, camera)
        baseline_items = len(canvas.calls)
        created = sum(method.startswith('create_') for method, _, _ in canvas.calls)
        self.assertGreater(created, 50)
        for tick in range(1, 11):
            pose = {subject.id: ActorPose(x+tick*.08, y+tick*.03,
                                         'move', 'east')}
            renderer.draw(battle, frame, camera, poses=pose)
        new = canvas.calls[baseline_items:]
        self.assertEqual(renderer._scene_rebuilds, 1)
        self.assertEqual(renderer._actor_only_frames, 10)
        self.assertFalse(any(method.startswith('create_') or
                             method == 'delete' for method, _, _ in new))
        self.assertEqual(canvas.count('delete'), 1)
        self.assertGreaterEqual(canvas.count('move'), 11)
        self.assertEqual(battle.digest(), before)

    def test_selected_threats_camera_zoom_viewport_and_frames_invalidate(self):
        battle = Battle(self.content, 'garden', seed=9)
        frame = battle_frame(battle, (1, 2))
        canvas, renderer = self.make_renderer()
        base = Camera(54, 8, 8)
        renderer.draw(battle, frame, base)
        self.assertEqual(renderer._scene_rebuilds, 1)
        renderer.draw(battle, frame, base)
        self.assertEqual(renderer._scene_rebuilds, 1)
        renderer.draw(battle, replace(frame, selected=(2, 2)), base)
        self.assertEqual(renderer._scene_rebuilds, 2)
        renderer.draw(battle, replace(frame, danger=({'cell':[2, 2],
                                                     'kind':'cast'},)), base)
        self.assertEqual(renderer._scene_rebuilds, 3)
        renderer.draw(battle, frame, Camera(62, 8, 8))
        self.assertEqual(renderer._scene_rebuilds, 4)
        renderer.draw(battle, frame, Camera(62, -20, 8))
        self.assertEqual(renderer._scene_rebuilds, 5)
        canvas.width = 900
        renderer.draw(battle, frame, Camera(62, -20, 8))
        self.assertEqual(renderer._scene_rebuilds, 6)
        renderer.dispose()
        self.assertIsNone(renderer.geometry)
        self.assertIsNone(renderer._frame)
        renderer.draw(battle, frame, base)
        self.assertEqual(renderer._scene_rebuilds, 7)

    def test_animated_doorway_forces_only_cutaway_transition_redraws(self):
        source = add_blank_mission(self.content.to_dict(),
                                   'cache_studio', 'Cache studio', 12, 12)
        source = place_structure(source, 'cache_studio', 'Maison', (3, 3))
        content = Content.from_dict(source)
        battle = Battle(content, 'cache_studio', seed=7)
        frame = battle_frame(battle, (0, 0))
        canvas, renderer = self.make_renderer()
        actor = next(iter(battle.units))
        camera = Camera(54, 0, 0)
        renderer.draw(battle, frame, camera)
        initial = renderer._scene_rebuilds
        # A moving unit outside is decor-only and needs no terrain refresh.
        for x in (1.5, 1.7, 1.9):
            renderer.draw(battle, frame, camera, poses={
                actor.id: ActorPose(x, 4, 'move', 'east')})
        self.assertEqual(renderer._scene_rebuilds, initial)
        self.assertEqual(renderer._actor_only_frames, 3)
        # Crossing x=2 activates the roof cutaway due to fractional overlap.
        renderer.draw(battle, frame, camera, poses={
            actor.id: ActorPose(2.2, 4, 'move', 'east')})
        self.assertEqual(renderer._scene_rebuilds, initial+1)
        self.assertTrue(renderer._cutaways)
        self.assertTrue(renderer._cutaways[0])
        renderer.draw(battle, frame, camera, poses={
            actor.id: ActorPose(2.5, 4, 'move', 'east')})
        self.assertEqual(renderer._scene_rebuilds, initial+1)
        renderer.draw(battle, frame, camera, poses={
            actor.id: ActorPose(1.9, 4, 'move', 'west')})
        self.assertEqual(renderer._scene_rebuilds, initial+2)
        self.assertFalse(renderer._cutaways[0])
        self.assertTrue(architecture_instances(battle.board))

    def test_actor_group_ids_invalidate_when_actor_order_changes(self):
        battle = Battle(self.content, 'garden', seed=9)
        frame = battle_frame(battle, (1, 1))
        canvas, renderer = self.make_renderer()
        camera = Camera(54, 0, 0)
        renderer.draw(battle, frame, camera)
        self.assertEqual(renderer._scene_rebuilds, 1)
        # A reorder (rare during runtime, common during editor previews)
        # must discard positional actor-index cache rather than move wrong IDs.
        original = battle.units
        try:
            battle.units = list(reversed(original))
            renderer.draw(battle, frame, camera)
            self.assertEqual(renderer._scene_rebuilds, 2)
        finally:
            battle.units = original


if __name__ == '__main__':
    unittest.main()
