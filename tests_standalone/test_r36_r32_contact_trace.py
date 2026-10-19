"""R36.B3 R32 contact-trace certification: authoritative collider identity/faces."""
from __future__ import annotations

from copy import deepcopy
import unittest

from drawtemp.render.r32_contact_trace import trace_platform_contacts
from sporebound.platform_physics import PlatformPhysics
from tests_standalone.test_platform_physics_r32 import scene, block, step


class PhysicsContactTraceTests(unittest.TestCase):
    def test_exact_wall_face_from_successful_swept_aabb_event(self):
        room = scene(colliders=[
            block("floor", [0, 5000, 12000, 1000]),
            block("thin_wall", [3000, 3200, 2, 1800]),
        ])
        game = PlatformPhysics(room)
        found = None
        for _ in range(20):
            events = step(game, move=1)
            trace = trace_platform_contacts(room, game.snapshot(), events)
            if trace:
                found = trace[0]
                break
        self.assertIsNotNone(found)
        self.assertEqual(found["origin"], "r32_committed_collision")
        self.assertEqual(found["collider"], "thin_wall")
        self.assertEqual(found["kind"], "wall")
        self.assertEqual(found["normal"], [-1, 0])
        self.assertEqual(found["contact"], [3000, 4600])
        self.assertEqual(found["world_xy"], [3.0, 4.6])
        self.assertEqual(game.digest(),
                         PlatformPhysics.from_recording(
                             game.recording(), expected_scene=room).digest())

    def test_exact_landing_face_and_noncollision_events_ignored(self):
        room = scene()
        game = PlatformPhysics(room)
        self.assertEqual(trace_platform_contacts(room, game.snapshot(),
                                                  []), [])
        step(game, jump=True)
        land = None
        for _ in range(60):
            events = step(game)
            contacts = trace_platform_contacts(room, game.snapshot(), events)
            if contacts:
                land = contacts[0]
                break
        self.assertIsNotNone(land)
        self.assertEqual(land["kind"], "land")
        self.assertEqual(land["collider"], "floor")
        self.assertEqual(land["contact"], [1250, 5000])
        self.assertEqual(land["normal"], [0, -1])

    def test_forged_or_wrong_tick_contact_fails_closed(self):
        room = scene()
        game = PlatformPhysics(room)
        step(game)
        snap = game.snapshot()
        for invalid in (
            [{"kind": "wall", "collider": "missing", "tick": game.tick}],
            [{"kind": "land", "collider": "floor", "tick": game.tick + 1}],
            [{"kind": "wall", "collider": "floor", "tick": game.tick}],
            [{"kind": "ceiling", "collider": "world", "tick": game.tick}],
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                trace_platform_contacts(room, snap, invalid)
        after = game.recording()
        self.assertEqual(after, game.recording())

    def test_geometry_is_derived_from_committed_moving_collider_position(self):
        room = scene(hero={
            "pos": [2200, 1200], "size": [500, 800],
            "speed": 0, "jump": 0, "max_fall": 900, "coyote": 4,
        }, colliders=[
            block("moving", [1800, 3000, 1800, 100],
                  one_way=True, velocity=50, travel=[1800, 2400]),
        ])
        game = PlatformPhysics(room)
        snap = game.snapshot()
        self.assertEqual(snap["movers"]["moving"]["x"], 1800)
        # A jump or trigger is not a contact; no false visual impacts.
        self.assertEqual(trace_platform_contacts(room, snap, []), [])


if __name__ == "__main__":
    unittest.main()
