"""R36.B2 particle and light render plans are bounded and cosmetic only."""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch
import unittest

from drawtemp.player.action_controller import ActionPlayerController
from drawtemp.render.vfx2d import MAX_LIGHTS, MAX_PARTICLES, project_vfx
from tests_standalone.test_r36_committed_fx import encounter_scene


class Vfx2DTests(unittest.TestCase):
    def test_repeatable_render_plan_and_no_gameplay_delta(self):
        player = ActionPlayerController(encounter_scene())
        player.step(dx=1, attack=True)
        game = player.runtime.recording()
        before = player.state()
        self.assertTrue(before["vfx"]["particles"])
        self.assertTrue(before["vfx"]["lights"])
        self.assertEqual(before["vfx"], player.state()["vfx"])
        self.assertEqual(game, player.runtime.recording())
        before["vfx"]["particles"][0]["x"] = -222
        self.assertNotEqual(player.state()["vfx"]["particles"][0]["x"], -222)
        self.assertEqual(project_vfx(player.state()["fx"]), player.state()["vfx"])
        self.assertEqual(player.runtime.recording(), game)

    def test_bounded_bursts_and_accessible_fallback(self):
        active = [{"id": str(i), "actor": "hero", "kind": "impact",
                   "x": 4., "y": 6., "alpha": 0.8, "scale": 1.0}
                  for i in range(96)]
        result = project_vfx(active, density=3)
        self.assertEqual(len(result["particles"]), MAX_PARTICLES)
        self.assertEqual(len(result["lights"]), MAX_LIGHTS)
        disabled = project_vfx(active, density=0, lights_enabled=False)
        self.assertEqual(disabled["particles"], [])
        self.assertEqual(disabled["lights"], [])
        quiet = project_vfx(active, reduced_motion=True)
        self.assertEqual(quiet["particles"], [])
        self.assertEqual(quiet["lights"], [])

    def test_fail_closed_on_invalid_profile_and_effect(self):
        data = [{"id": "tick:1", "actor": "hero", "kind": "slash",
                 "x": 1, "y": 1, "alpha": .5, "scale": 1.0}]
        for kwargs in ({"density": True}, {"density": 4},
                       {"ambient_alpha": float("nan")},
                       {"reduced_motion": 1}, {"lights_enabled": None}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                project_vfx(data, **kwargs)
        for key, value in (("kind", "execute"), ("alpha", 2.),
                           ("x", float("inf")), ("scale", 0)):
            bad = deepcopy(data)
            bad[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                project_vfx(bad)

    def test_particle_coordinates_are_stable_across_python_calls(self):
        particle = {"id": "12:0", "actor": "hero", "kind": "dust",
                    "x": 1.25, "y": 2.5, "alpha": .75, "scale": 1}
        a = project_vfx([particle])
        b = project_vfx([deepcopy(particle)])
        self.assertEqual(a, b)
        self.assertEqual(len(a["particles"]), 6)
        self.assertEqual(a["lights"], [])


if __name__ == "__main__":
    unittest.main()
