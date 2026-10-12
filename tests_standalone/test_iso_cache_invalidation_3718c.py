"""Regression gates for 3.7.18C incremental isometric redraw."""
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.iso_battle_view import IsoBattleCanvas
from sporebound.model import Content
from sporebound.presentation import Camera, battle_frame
from sporebound.visual_motion import ActorPose


class CanvasStub:
    def __init__(self):
        self.calls = []
    def winfo_width(self):
        return 800
    def winfo_height(self):
        return 600
    def __getattr__(self, name):
        if name.startswith(('create_', 'tag_', 'move', 'delete', 'configure')):
            def record(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return len(self.calls)
            return record
        raise AttributeError(name)


class IncrementalSceneTests(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(Content.load(DEFAULT_CONTENT), 'garden', seed=9)
        self.frame = battle_frame(self.battle, (2, 2))
        self.camera = Camera(52, 0, 0)
        self.canvas = CanvasStub()
        self.renderer = IsoBattleCanvas(self.canvas)
        for atlas in (self.renderer.terrain, self.renderer.props,
                      self.renderer.buildings, self.renderer.fortifications):
            atlas._unavailable = True

    def test_identical_snapshot_reuses_scene_and_motion_moves_only_actor_tags(self):
        digest = self.battle.digest()
        self.renderer.draw(self.battle, self.frame, self.camera)
        self.assertEqual(self.renderer._scene_rebuilds, 1)
        first = self.battle.units[0]
        poses = {first.id: ActorPose(first.pos[0] + .25, first.pos[1],
                                     'move', 'east')}
        self.canvas.calls.clear()
        self.renderer.draw(self.battle, self.frame, self.camera, poses=poses)
        self.assertEqual(self.renderer._scene_rebuilds, 1)
        self.assertEqual(self.renderer._actor_only_frames, 1)
        self.assertFalse(any(name.startswith('create_') or name == 'delete'
                             for name, _, _ in self.canvas.calls))
        self.assertTrue(any(name == 'move' and str(args[0]).startswith('iso_actor_unit_')
                            for name, args, _ in self.canvas.calls))
        self.assertEqual(self.battle.digest(), digest)

    def test_hp_change_invalidates_cached_actor_labels_even_with_same_frame(self):
        self.renderer.draw(self.battle, self.frame, self.camera)
        unit = self.battle.units[0]
        with patch.object(self.renderer, '_actor_state', wraps=self.renderer._actor_state) as tracked:
            # Mutable render-only attributes can change between redraws without
            # a new BattleFrame. A cached HP label must not survive that change.
            previous = self.renderer._unit_state
            changed = list(previous)
            changed[0] = (*changed[0][:-1], changed[0][-1]-1)
            tracked.return_value = tuple(changed)
            self.renderer.draw(self.battle, self.frame, self.camera)
        self.assertEqual(self.renderer._scene_rebuilds, 2)

    def test_camera_or_selection_changes_force_full_redraw(self):
        self.renderer.draw(self.battle, self.frame, self.camera)
        self.renderer.draw(self.battle, self.frame, Camera(60, 0, 0))
        self.assertEqual(self.renderer._scene_rebuilds, 2)
        self.renderer.draw(self.battle, battle_frame(self.battle, (3, 3)),
                           Camera(60, 0, 0))
        self.assertEqual(self.renderer._scene_rebuilds, 3)
        self.renderer.dispose()
        self.assertEqual(self.renderer._unit_state, ())


if __name__ == '__main__':
    unittest.main()
