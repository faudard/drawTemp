"""R26.C shared R3 top-down projection, culling and exact 60 Hz pacing."""
import unittest

from drawtemp.player.action_clock import ActionStepClock
from drawtemp.player.action_controller import demo_scene
from drawtemp.render import (Camera, IsoProjection, TopDownProjection,
                             TileChunkIndex, fingerprint, pick, render_items,
                             scene_from_action, scene_from_mission)
from drawtemp.sdk.reference import reference_project
from sporebound.action_runtime import ActionRuntime


class R26CTopDownProjectionTests(unittest.TestCase):
    def test_projection_inverse_at_fractional_world_coordinates_and_pick(self):
        projection = TopDownProjection()
        for x in (0, .125, 1.0, 6.825, 10.25):
            for y in (0, .5, 3.3, 8.0):
                px, py = projection.project(x, y)
                world = projection.unproject(px, py)
                self.assertAlmostEqual(world[0], x)
                self.assertAlmostEqual(world[1], y)
        self.assertEqual(projection.pick(*projection.project(3, 5), 11, 9), (3, 5))
        self.assertEqual(projection.pick(*projection.project(3.49, 5.49), 11, 9),
                         (3, 5))
        self.assertIsNone(projection.pick(-34, 0, 11, 9))
        self.assertIsNone(projection.pick(9999, 9999, 11, 9))

    def test_scene_snapshot_is_detached_and_preserves_subtile_player_motion(self):
        game = ActionRuntime(demo_scene())
        initial = scene_from_action(game)
        actor = next(row for row in initial["actors"] if row["id"] == "hero")
        self.assertEqual((actor["x"], actor["y"]), (1, 2))
        game.step({"tick": 1, "dx": 1})
        later = scene_from_action(game)
        actor = next(row for row in later["actors"] if row["id"] == "hero")
        self.assertAlmostEqual(actor["x"], 1.16)
        self.assertAlmostEqual(actor["y"], 2.0)
        self.assertNotEqual(fingerprint(initial), fingerprint(later))
        self.assertEqual(initial["revision"], 0)
        self.assertEqual(later["revision"], 1)
        later["actors"][0]["x"] = -500
        later["objects"][0]["open"] = True
        self.assertEqual(game.hero["pos"], [1660, 2500])
        self.assertFalse(game.objects["supply"]["opened"])

    def test_shared_renderer_rows_pick_camera_follow_and_culling(self):
        runtime = ActionRuntime(demo_scene())
        scene = scene_from_action(runtime)
        projection = TopDownProjection()
        camera = Camera(width=900, height=600)
        hero = next(row for row in scene["actors"] if row["id"] == "hero")
        camera.center(*projection.project(hero["x"], hero["y"]))
        index = TileChunkIndex(scene)
        rows = render_items(scene, camera, projection, tile_index=index)
        self.assertIn("hero", {row["id"] for row in rows})
        self.assertIn("wolf", {row["id"] for row in rows})
        self.assertIn("supply", {row["id"] for row in rows})
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        self.assertTrue(any(row["kind"] == "tile" for row in rows))
        tile_depths = [row["zOrder"] for row in rows if row["kind"] == "tile"]
        actor_depths = [row["zOrder"] for row in rows if row["kind"] == "actor"]
        self.assertGreater(min(actor_depths), max(tile_depths),
                           "Ground tiles must not conceal top-down actors")
        sx, sy = camera.screen(*projection.project(hero["x"], hero["y"]))
        self.assertEqual(pick(scene, camera, sx, sy, projection),
                         {"kind": "actor", "id": "hero"})
        sx, sy = camera.screen(*projection.project(1, 3))
        self.assertEqual(pick(scene, camera, sx, sy, projection),
                         {"kind": "object", "id": "supply"})
        self.assertEqual([row["id"] for row in rows],
                         [row["id"] for row in render_items(
                             scene, camera, projection, tile_index=index)])
        camera.zoom_at(1.8, 200, 200)
        sx, sy = camera.screen(*projection.project(6, 6))
        self.assertEqual(projection.pick(*camera.world(sx, sy),
                                         scene["width"], scene["height"]), (6, 6))
        result = pick(scene, camera, sx, sy, projection)
        self.assertEqual(result, {"kind": "tile", "cell": [6, 6]})

    def test_legacy_isometric_projection_and_scene_stay_unchanged(self):
        content, _ = reference_project()
        mission = next(iter(content.missions.values()))
        left = scene_from_mission(mission)
        iso = IsoProjection()
        self.assertEqual(iso.project(3, 2), (48.0, 120.0))
        self.assertEqual(fingerprint(left), fingerprint(scene_from_mission(mission)))
        self.assertEqual(len(left["tiles"]), mission.board.width * mission.board.height)


class R26CClockTests(unittest.TestCase):
    @staticmethod
    def simulate(polls):
        clock = ActionStepClock(hz=60)
        emitted = []
        previous = 0
        for index in range(1, polls + 1):
            now = index * 1_000_000_000 // polls
            emitted.append(clock.advance(now - previous))
            previous = now
        return sum(emitted)

    def test_equal_sim_ticks_at_30_60_120_144_and_240_polls_per_second(self):
        for fps in (30, 60, 120, 144, 240):
            with self.subTest(fps=fps):
                self.assertEqual(self.simulate(fps), 60)

    def test_catchup_is_bounded_and_pause_flushes_old_time(self):
        clock = ActionStepClock(hz=60, max_catchup=4)
        self.assertEqual(clock.advance(5_000_000_000), 4)
        self.assertEqual(clock.advance(0), 0)
        self.assertEqual(clock.advance(16_666_667), 1)
        clock.reset()
        self.assertEqual(clock.advance(0), 0)
        self.assertEqual(clock.advance(16_666_667), 1)

    def test_reject_noninteger_and_negative_deltas(self):
        clock = ActionStepClock()
        for elapsed in (-1, 1.5, True, None):
            with self.subTest(elapsed=elapsed), self.assertRaises(ValueError):
                clock.advance(elapsed)
        with self.assertRaises(ValueError):
            ActionStepClock(hz=59)
        with self.assertRaises(ValueError):
            ActionStepClock(max_catchup=0)


if __name__ == "__main__":
    unittest.main()
