"""R36.B3 bounded wall-occluded cell lighting is stable and visual-only."""
from __future__ import annotations

from copy import deepcopy
import unittest

from drawtemp.render.cell_lighting import project_cell_lighting
from drawtemp.render.iso_scene import (
    scene_from_action, render_items, Camera, TopDownProjection,
)
from sporebound.action_runtime import ActionRuntime
from tests_standalone.test_r36_committed_fx import encounter_scene


class CellLightingTests(unittest.TestCase):
    def test_authored_wall_blocks_visual_rays_without_touching_action_logic(self):
        scene = encounter_scene()
        scene["walls"] = [[2, 3]]
        light = {"x": 1.0, "y": 3.0, "radius": 180., "alpha": .8}
        grid = project_cell_lighting(scene, [light])
        self.assertGreater(grid["1:3"], 0)
        self.assertGreater(grid["2:3"], 0)  # the occluder itself can be lit
        self.assertNotIn("3:3", grid)          # but it hides following cells
        self.assertEqual(grid, project_cell_lighting(deepcopy(scene), [dict(light)]))
        runtime = ActionRuntime(scene)
        before = runtime.recording()
        projected = scene_from_action(runtime)
        projected["light_cells"] = grid
        rows = render_items(projected, Camera(), TopDownProjection())
        lighting = {(r["x"], r["y"]): r["lightShade"] for r in rows
                    if r["kind"] == "tile"}
        self.assertLess(lighting[(1, 3)], lighting[(3, 3)])
        self.assertEqual(before, runtime.recording())
        old_view = scene_from_action(runtime)
        old_rows = render_items(old_view, Camera(), TopDownProjection())
        self.assertNotIn("lightShade", next(r for r in old_rows
                                           if r["kind"] == "tile"))

    def test_limited_lights_and_bad_geometry_fail_closed(self):
        scene = encounter_scene()
        good = {"x": 1., "y": 1., "radius": 80, "alpha": .7}
        for lights in ([good] * 9,
                       [{**good, "radius": -1}],
                       [{**good, "alpha": float("inf")}],
                       [{**good, "x": -1}],
                       [{**good, "y": True}]):
            with self.subTest(lights=lights), self.assertRaises(ValueError):
                project_cell_lighting(scene, lights)
        bad_scene = deepcopy(scene)
        bad_scene["walls"] = [[200, 1]]
        with self.assertRaises(ValueError):
            project_cell_lighting(bad_scene, [good])
        with self.assertRaises(ValueError):
            project_cell_lighting(scene, "not lights")

    def test_multiple_lights_are_bounded_and_no_simulation_authority(self):
        scene = encounter_scene()
        light = {"x": 1, "y": 1, "radius": 45., "alpha": .1}
        one = project_cell_lighting(scene, [light])
        two = project_cell_lighting(scene, [light, dict(light)])
        self.assertGreater(two["1:1"], one["1:1"])
        self.assertLessEqual(max(two.values()), 1.)
        game = ActionRuntime(scene)
        for tick in range(1, 8):
            game.step({"tick": tick})
            project_cell_lighting(scene, [light])
        self.assertEqual(game.recording(),
                         ActionRuntime.from_recording(game.recording()).recording())


if __name__ == "__main__":
    unittest.main()
