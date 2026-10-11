"""3.5.1 — deterministic, headless animation contract."""
from dataclasses import replace
import unittest

from sporebound.assets import AssetRegistry
from sporebound.presentation import ActorView, BattleFrame
from sporebound.visual_motion import MotionDirector, animation_sprite_id


def frame(*, tick=1, pos=(0, 0), hp=10, alive=True, events=(), mission="castle"):
    actor = ActorView("jeanne", "Jeanne", "player", pos, (1, 1),
                      hp, 10, 3, 3, alive, True, ())
    return BattleFrame(mission, 4, 4, tick, "jeanne", False, None,
                       (), (actor,), (), None, (), (), tuple(events))


class MotionTests(unittest.TestCase):
    def test_movement_samples_without_modifying_source(self):
        director = MotionDirector(200)
        first = frame()
        second = frame(pos=(2, 0), events=({"kind": "move", "unit": "jeanne"},))
        director.observe(first, 1000)
        director.observe(second, 1100)
        self.assertEqual(director.poses(1100)["jeanne"].x, 0)
        pose = director.poses(1200)["jeanne"]
        self.assertEqual((pose.x, pose.y, pose.action, pose.direction),
                         (1., 0., "move", "east"))
        self.assertTrue(director.active(1200))
        self.assertFalse(director.active(1300))
        self.assertEqual(director.poses(1300)["jeanne"].x, 2)
        self.assertEqual(first.actors[0].pos, (0, 0))
        self.assertEqual(second.actors[0].pos, (2, 0))

    def test_selection_redraw_does_not_restart_animation(self):
        director = MotionDirector()
        director.observe(frame(), 100)
        director.observe(frame(pos=(0, -1)), 200)
        director.observe(replace(frame(pos=(0, -1)), selected=(2, 2)), 310)
        self.assertEqual(director.elapsed_ms(310), 110)
        self.assertEqual(director.poses(310)["jeanne"].direction, "north")

    def test_attack_hit_and_defeat_are_presentation_only(self):
        director = MotionDirector()
        director.observe(frame(events=({"kind": "activation"},)), 0)
        director.observe(frame(events=({"kind": "activation"},
                                       {"kind": "skill", "unit": "jeanne"})), 200)
        self.assertEqual(director.poses(200)["jeanne"].action, "attack")
        director.observe(frame(hp=5), 300)
        self.assertEqual(director.poses(300)["jeanne"].action, "hit")
        director.observe(frame(hp=0, alive=False), 400)
        self.assertEqual(director.poses(400)["jeanne"].action, "defeat")
        self.assertEqual(director.poses(900)["jeanne"].action, "defeat")

    def test_mission_switch_and_tick_rollback_reset_interpolation(self):
        director = MotionDirector()
        director.observe(frame(tick=2), 0)
        director.observe(frame(tick=3, pos=(2, 2)), 100)
        director.observe(frame(tick=1, pos=(1, 1)), 110)
        self.assertEqual(director.poses(111)["jeanne"].x, 1)
        self.assertFalse(director.active(111))
        director.observe(frame(tick=1, mission="other"), 120)
        self.assertFalse(director.active(120))

    def test_animation_frames_bind_by_actor_then_team_and_wrap(self):
        registry = AssetRegistry({"version": 1, "entries": [
            {"id": "step1", "kind": "sprite", "path": "art/a.png"},
            {"id": "step2", "kind": "sprite", "path": "art/b.png"},
            {"id": "idle", "kind": "sprite", "path": "art/c.png"},
            {"id": "walk", "kind": "animation", "loop": True, "frames": [
                {"sprite": "step1", "duration_ms": 100},
                {"sprite": "step2", "duration_ms": 200}]},
            {"id": "rest", "kind": "animation", "loop": True, "frames": [
                {"sprite": "idle", "duration_ms": 150}]}
        ], "bindings": {"animation": {
            "jeanne_move_east": "walk", "player_idle": "rest"}}})
        choose = lambda pose, ms: animation_sprite_id(
            registry, "jeanne", "player", pose, "east", ms)
        self.assertEqual(choose("move", 0), "step1")
        self.assertEqual(choose("move", 100), "step2")
        self.assertEqual(choose("move", 301), "step1")
        self.assertEqual(choose("attack", 0), "idle")
        self.assertIsNone(animation_sprite_id(None, "j", "p", "idle", "south", 0))


if __name__ == "__main__":
    unittest.main()
