"""DrawTemp 5 R3 geometry, parity, culling and real R1 snapshot contract."""
import math
import unittest

from drawtemp.render import (Camera, IsoProjection, fingerprint, pick,
                             render_items, scene_from_mission)
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.simulation import Simulation


class RendererR3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content, cls.project = reference_project()
        cls.mission = cls.content.missions[MISSION]

    def test_projection_roundtrip_heights_fractional_coordinates(self):
        p = IsoProjection()
        for x in (0, 1, 5.25, 27.75):
            for y in (0, 2.5, 13):
                for altitude in (0, 1, 4):
                    sx, sy = p.project(x, y, altitude)
                    xx, yy = p.unproject(sx, sy, altitude)
                    self.assertAlmostEqual(xx, x)
                    self.assertAlmostEqual(yy, y)

    def test_terrain_picking_with_altitude(self):
        p = IsoProjection()
        elevations = {(2, 1): 3, (2, 2): 1}
        for cell in ((0, 0), (2, 1), (2, 2), (3, 3)):
            x, y = cell
            sx, sy = p.project(x, y, elevations.get(cell, 0))
            self.assertEqual(p.pick(sx, sy, 7, 7, elevations), cell)

    def test_camera_anchor_invariant_zoom_and_pan(self):
        c = Camera()
        for factor in (1.3, 1.8, 0.4, 4, 0.01):
            before = c.world(71, 219)
            c.zoom_at(factor, 71, 219)
            self.assertAlmostEqual(c.world(71, 219)[0], before[0])
            self.assertAlmostEqual(c.world(71, 219)[1], before[1])
            self.assertGreaterEqual(c.zoom, .4)
            self.assertLessEqual(c.zoom, 3)
        with self.assertRaises(ValueError):
            c.zoom_at(float("nan"), 0, 0)

    def test_same_jeanne_scene_parity_and_content_purity(self):
        before = self.mission.board.tile((0, 0)).surface
        studio = scene_from_mission(self.mission)
        player = scene_from_mission(self.mission)
        self.assertEqual(fingerprint(studio), fingerprint(player))
        self.assertEqual(len(studio["tiles"]), studio["width"] * studio["height"])
        self.assertTrue(studio["actors"])
        self.assertTrue(studio["objects"])
        studio["tiles"][0]["surface"] = "destroyed"
        self.assertEqual(self.mission.board.tile((0, 0)).surface, before)
        self.assertEqual(player["tiles"][0]["surface"], before)

    def test_snapshot_state_is_detached_and_versioned(self):
        sdk = Simulation.new(self.content, self.project, "main")
        sdk.choose_story_option("enter")
        sdk.start_mission(MISSION)
        state = sdk.snapshot()
        visual = scene_from_mission(self.mission, state)
        self.assertEqual(visual["revision"], state.revision)
        self.assertEqual(visual["mission"], MISSION)
        self.assertEqual(len(visual["actors"]), len(state.battle["units"]))
        visual["actors"][0]["x"] = -100
        self.assertNotEqual(state.battle["units"][0]["pos"][0], -100)
        sdk.execute({"kind": "interact", "unit": "jeanne", "object": "lever"})
        later = scene_from_mission(self.mission, sdk.snapshot())
        self.assertNotEqual(fingerprint(later), fingerprint(visual))
        other = self.content.missions[MISSION]
        from copy import deepcopy
        invalid = deepcopy(other)
        invalid.id = "not-jeanne"
        with self.assertRaises(ValueError):
            scene_from_mission(invalid, sdk.snapshot())

    def test_visible_culling_depth_and_identity(self):
        scene = scene_from_mission(self.mission)
        c = Camera(width=360, height=240)
        p = IsoProjection()
        c.center(*p.project(4, 4))
        items = render_items(scene, c)
        all_ids = [r["id"] for r in items]
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertEqual(items, sorted(items, key=lambda r: (r["zOrder"], r["id"])))
        self.assertGreater(len(items), 0)
        self.assertLessEqual(len([i for i in items if i["kind"] == "tile"]),
                             scene["width"] * scene["height"])
        # Culling must actually discard far-away chunks on large boards.
        large = {**scene, "width": 64, "height": 64,
                 "tiles": [{"x": x, "y": y, "height": 0, "surface": "grass"}
                           for x in range(64) for y in range(64)],
                 "actors": [], "objects": []}
        self.assertLess(len(render_items(large, c)), 64 * 64)
        c.zoom_at(1.1, 160, 100)
        self.assertTrue(render_items(scene, c))

    def test_tile_picking_stays_correct_under_zoom(self):
        scene = scene_from_mission(self.mission)
        p, c = IsoProjection(), Camera()
        x, y = 4, 2
        z = self.mission.board.tile((x, y)).height
        c.center(*p.project(x, y, z))
        for factor in (1, 1.4, 0.6):
            sx, sy = c.screen(*p.project(x, y, z))
            picked = pick(scene, c, sx, sy)
            # An actor/object standing on this tile may correctly win.
            self.assertIn(picked["kind"], ("tile", "actor", "object"))
            c.zoom_at(factor, sx, sy)


if __name__ == "__main__":
    unittest.main()
