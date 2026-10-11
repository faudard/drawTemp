"""3.7.6 renderer workload uses a genuine authored Jeanne tactical projection."""
import unittest

from scripts.benchmark_player_canvas_376 import CONTENT, build_scene


class RealCanvasBenchmarkTests(unittest.TestCase):
    def test_jeanne_scene_is_authentic_and_does_not_change_battle(self):
        frame, registry, battle, digest = build_scene()
        self.assertEqual(frame.mission, battle.mission.name)
        self.assertEqual(len(frame.tiles), battle.board.width * battle.board.height)
        self.assertEqual(len(frame.actors), len(battle.units))
        self.assertTrue(frame.actors)
        self.assertEqual(battle.digest(), digest)
        self.assertEqual(registry.diagnostics(CONTENT), [])

    def test_stress_copies_are_only_render_projections(self):
        for number in (20, 80, 200):
            with self.subTest(number=number):
                frame, _registry, battle, digest = build_scene(number)
                self.assertEqual(len(frame.actors), number)
                self.assertEqual(len({actor.id for actor in frame.actors}), number)
                self.assertLess(len(battle.units), number)
                self.assertEqual(battle.digest(), digest)

    def test_undersized_projection_is_rejected(self):
        frame, _registry, _battle, _digest = build_scene()
        with self.assertRaises(ValueError):
            build_scene(len(frame.actors) - 1)


if __name__ == "__main__":
    unittest.main()
