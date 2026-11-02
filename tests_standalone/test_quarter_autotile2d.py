"""Quarter-tile topology, sprite PNG and R3 projection regression tests."""
from __future__ import annotations

import struct
import unittest
from zlib import decompress

from drawtemp.assets.topdown_tileset import atlas_rect, starter_tileset_png
from drawtemp.render.autotile2d import (
    MATERIALS, affected_cells, decode_key, encode_key, mask_alpha,
    overlays_for_key, quadrant_overlays, tile_key,
)


def tiles(size=5):
    return {(x, y): {"surface": "grass", "height": 0}
            for y in range(size) for x in range(size)}


def overlays(m, q):
    return [(x.material, x.mask) for x in m[q]]


class AutotileQuarterTests(unittest.TestCase):
    def test_eight_neighbors_and_exact_four_quadrants(self):
        cells = tiles()
        cells[(2, 1)]["surface"] = "stone"  # N
        cells[(1, 2)]["surface"] = "dirt"  # W
        cells[(1, 1)]["surface"] = "dirt"  # NW
        key = tile_key(cells, 2, 2)
        self.assertEqual(len(key), 10)
        self.assertEqual(decode_key(key)[0], "grass")
        quarters = overlays_for_key(key)
        self.assertEqual(len(quarters), 4)
        self.assertEqual(overlays(quarters, 0), [("dirt", 6), ("stone", 1)])
        self.assertEqual(overlays(quarters, 1), [("stone", 1)])
        self.assertEqual(overlays(quarters, 2), [("dirt", 2)])
        self.assertEqual(overlays(quarters, 3), [])

    def test_diagonal_only_rounds_corner_and_not_cardinal_edges(self):
        cells = tiles()
        cells[(1, 1)]["surface"] = "dirt"
        key = tile_key(cells, 2, 2)
        q = overlays_for_key(key)
        self.assertEqual(overlays(q, 0), [("dirt", 4)])
        self.assertEqual(overlays(q, 1), [])
        self.assertEqual(mask_alpha("nw", 4, 0, 0), 255)
        self.assertEqual(mask_alpha("nw", 4, 31, 15), 0)
        self.assertEqual(mask_alpha("nw", 0, 0, 0), 0)

    def test_shared_edge_is_full_opacity_at_neighbor_boundary(self):
        self.assertEqual(mask_alpha("nw", 1, 20, 0), 255)
        self.assertEqual(mask_alpha("ne", 1, 9, 0), 255)
        self.assertEqual(mask_alpha("sw", 1, 13, 31), 255)
        self.assertEqual(mask_alpha("se", 2, 31, 16), 255)
        self.assertEqual(mask_alpha("nw", 1, 20, 31), 0)

    def test_cliffs_water_and_bridges_do_not_get_land_overlay(self):
        cells = tiles()
        cells[(2, 1)] = {"surface": "rock", "height": 1}
        self.assertEqual(overlays_for_key(tile_key(cells, 2, 2)),
                         ((), (), (), ()))
        cells[(2, 2)] = {"surface": "water", "height": 0}
        self.assertEqual(overlays_for_key(tile_key(cells, 2, 2)),
                         ((), (), (), ()))
        cells[(2, 2)]["surface"] = "bridge"
        self.assertEqual(overlays_for_key(tile_key(cells, 2, 2)),
                         ((), (), (), ()))

    def test_border_and_out_of_bounds_neighbors(self):
        cells = tiles(2)
        self.assertEqual(decode_key(tile_key(cells, 0, 0))[0], "grass")
        with self.assertRaises(ValueError):
            tile_key(cells, 3, 3)

    def test_decode_validation_and_determinism(self):
        neighbours = ("dirt", "dirt", "stone", "sand",
                      "stone", "grass", "rock", "cobble")
        key = encode_key("grass", neighbours, 1)
        self.assertEqual(decode_key(key), ("grass", neighbours, 1))
        self.assertEqual(encode_key(*decode_key(key)), key)
        for invalid in ("", "0"*9, "9"*10, "../file.png", "0000000002"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    decode_key(invalid)
        self.assertEqual(len(MATERIALS), 8)

    def test_local_dirty_invalidation_includes_diagonals(self):
        self.assertEqual(affected_cells([(2, 2)], 6, 6),
                         frozenset((x, y) for x in (1, 2, 3)
                                   for y in (1, 2, 3)))
        self.assertEqual(len(affected_cells([(0, 0)], 2, 2)), 4)

    def test_sprite_sheet_is_real_png_with_native_crops(self):
        data = starter_tileset_png()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (1024, 64))
        self.assertEqual(starter_tileset_png(), data)  # cached deterministic bytes
        self.assertEqual(atlas_rect("grass", 0), (0, 0, 64, 64))
        self.assertEqual(atlas_rect("bridge", 1), (960, 0, 64, 64))
        with self.assertRaises(ValueError):
            atlas_rect("unknown", 0)

    def test_normal_iso_render_rows_remain_without_autotile_key(self):
        from drawtemp.sdk.reference import reference_project
        from drawtemp.render.iso_scene import (
            Camera, IsoProjection, TopDownProjection, render_items,
            scene_from_mission,
        )
        content, _ = reference_project()
        mission = next(iter(content.missions.values()))
        scene = scene_from_mission(mission)
        camera = Camera(width=900, height=700)
        iso_rows = render_items(scene, camera, IsoProjection())
        self.assertTrue(any(row["kind"] == "tile" for row in iso_rows))
        self.assertFalse(any("autotileKey" in row for row in iso_rows))
        top_rows = render_items(scene, camera, TopDownProjection())
        tile_rows = [row for row in top_rows if row["kind"] == "tile"]
        self.assertTrue(tile_rows)
        self.assertTrue(all(len(row["autotileKey"]) == 10 for row in tile_rows))


if __name__ == "__main__":
    unittest.main()
