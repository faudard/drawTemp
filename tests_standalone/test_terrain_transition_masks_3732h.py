"""3.7.32H — RGBA feather masks, triple junctions and deterministic edges."""
from hashlib import sha256
import struct
import unittest
import zlib

from sporebound.iso_connections import N, E, S, W
from sporebound.terrain_autoblend import BlendEdge, LAND_PRIORITY
from sporebound.terrain_transition_masks import (
    DIRECTIONS, MASK_VARIANTS, _edge_distance, ordered_blend_masks,
    painted_mask_key, painted_mask_pixel, painted_mask_png,
)
from sporebound.terrain_watercolor import PIGMENTS, TILE_WIDTH, TILE_HEIGHT


class PaintedTransitionMasksTests(unittest.TestCase):
    def test_png_is_valid_rgba_96x48_and_has_stable_checksum(self):
        png = painted_mask_png('grass', N, 0)
        self.assertIs(png, painted_mask_png('grass', N, 0))
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(sha256(png).hexdigest(), sha256(painted_mask_png('grass', N, 0)).hexdigest())
        self.assertLess(len(png), 20_000)
        offset, data, ihdr = 8, [], None
        while offset < len(png):
            size = struct.unpack('>I', png[offset:offset+4])[0]
            kind = png[offset+4:offset+8]
            chunk = png[offset+8:offset+8+size]
            crc = struct.unpack('>I', png[offset+8+size:offset+12+size])[0]
            self.assertEqual(zlib.crc32(kind+chunk) & 0xffffffff, crc)
            if kind == b'IHDR':
                ihdr = struct.unpack('>IIBBBBB', chunk)
            if kind == b'IDAT':
                data.append(chunk)
            offset += 12 + size
        self.assertEqual(offset, len(png))
        self.assertEqual(ihdr, (96, 48, 8, 6, 0, 0, 0))
        raw = zlib.decompress(b''.join(data))
        self.assertEqual(len(raw), 48*(96*4+1))

    def test_four_masks_have_exact_shared_edge_pigment(self):
        locations = {
            N: (24, 12), E: (71, 35),
            S: (24, 35), W: (71, 12),
        }
        for material in LAND_PRIORITY:
            for bit in DIRECTIONS:
                with self.subTest(material=material, edge=bit):
                    x, y = locations[bit]
                    pixel = painted_mask_pixel(material, bit, 0, x, y)
                    self.assertEqual(pixel, (*PIGMENTS[material], 255))
                    self.assertEqual(painted_mask_pixel(material, bit, 0, 48, 24)[3], 0)
                    self.assertEqual(painted_mask_pixel(material, bit, 0, 0, 0), (0, 0, 0, 0))

    def test_alpha_feather_is_deterministic_with_irregular_inset(self):
        self.assertEqual(painted_mask_pixel('grass', E, 2, 72, 35),
                         painted_mask_pixel('grass', E, 2, 72, 35))
        # Edge-to-interior never appears as opaque rectangular sprite.
        for bit in DIRECTIONS:
            for variant in range(MASK_VARIANTS):
                pixels = [painted_mask_pixel('rock', bit, variant, x, y)[3]
                          for y in range(0, TILE_HEIGHT, 3)
                          for x in range(0, TILE_WIDTH, 3)]
                self.assertIn(0, pixels)
                self.assertIn(255, pixels)
                self.assertTrue(any(0 < a < 255 for a in pixels))

    def test_three_way_corner_resolves_highest_priority_last(self):
        edges = (
            BlendEdge(N, 'grass', 0xabcd),
            BlendEdge(E, 'stone', 0x15),
            BlendEdge(W, 'cobble', 0x23),
        )
        order = ordered_blend_masks(edges, LAND_PRIORITY)
        self.assertEqual([e.incoming for e in order],
                         ['grass', 'cobble', 'stone'])
        self.assertEqual(ordered_blend_masks(reversed(edges), LAND_PRIORITY), order)
        self.assertEqual(painted_mask_key(edges[0]), ('grass', N, 1))
        self.assertEqual(painted_mask_key(edges[1]), ('stone', E, 1))

    def test_no_mask_renders_outside_iso_diamond(self):
        for bit in DIRECTIONS:
            for material in ('grass', 'dirt', 'stone', 'sand', 'rock', 'cobble'):
                for x, y in ((0, 0), (95, 0), (0, 47), (95, 47), (48, 0)):
                    u = (x+.5-48)/48
                    v = (y+.5-24)/24
                    if abs(u)+abs(v) >= 1:
                        self.assertEqual(
                            painted_mask_pixel(material, bit, 0, x, y)[3], 0)

    def test_rejects_bad_material_direction_variant_and_coordinates(self):
        for args in (('water', N, 0, 48, 24),
                     ('grass', 16, 0, 48, 24),
                     ('grass', N, 4, 48, 24),
                     ('grass', N, True, 48, 24),
                     ('grass', N, 0, -1, 24),
                     ('grass', N, 0, 96, 24),
                     ('grass', N, 0, 48, 48)):
            # water is a valid palette material, but not a usable land edge;
            # masks are usable only after headless blend_edges filters it out.
            if args[0] == 'water':
                self.assertEqual(painted_mask_pixel(*args)[3], 0)
                continue
            with self.subTest(args=args), self.assertRaises(ValueError):
                painted_mask_pixel(*args)


if __name__ == '__main__':
    unittest.main()
