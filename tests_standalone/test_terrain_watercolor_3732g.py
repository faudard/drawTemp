"""3.7.32G — fully deterministic watercolor materials and edge-safe pixels."""
import hashlib
import struct
import unittest
import zlib

from sporebound.terrain_watercolor import (
    MATERIALS, PIGMENTS, TILE_WIDTH, TILE_HEIGHT, VARIANTS,
    pixel, watercolor_atlas_png, watercolor_atlas_sha256,
    write_watercolor_atlas,
)


class WatercolorMaterialsTests(unittest.TestCase):
    def test_valid_rgba_png_reproducible_atlas_geometry_and_crc(self):
        data = watercolor_atlas_png()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         watercolor_atlas_sha256())
        self.assertIs(data, watercolor_atlas_png())  # process-wide cache
        self.assertLess(len(data), 300_000)  # compressed cache stays modest
        offset, decoded = 8, []
        header = None
        while offset < len(data):
            size = struct.unpack('>I', data[offset:offset+4])[0]
            kind = data[offset+4:offset+8]
            payload = data[offset+8:offset+8+size]
            checksum = struct.unpack('>I', data[offset+8+size:offset+12+size])[0]
            self.assertEqual(zlib.crc32(kind+payload) & 0xffffffff, checksum)
            if kind == b'IHDR':
                header = struct.unpack('>IIBBBBB', payload)
            elif kind == b'IDAT':
                decoded.append(payload)
            elif kind == b'IEND':
                self.assertEqual(offset+12, len(data))
            offset += size+12
        self.assertEqual(header, (len(MATERIALS)*VARIANTS*TILE_WIDTH,
                                  TILE_HEIGHT, 8, 6, 0, 0, 0))
        raw = zlib.decompress(b''.join(decoded))
        self.assertEqual(len(raw), TILE_HEIGHT*(header[0]*4+1))
        self.assertTrue(all(raw[y*(header[0]*4+1)] == 0
                            for y in range(TILE_HEIGHT)))

    def test_all_eight_materials_are_painted_and_alpha_diamond_shaped(self):
        self.assertEqual(len(MATERIALS), 8)
        self.assertEqual(set(MATERIALS), set(PIGMENTS))
        for name in MATERIALS:
            for variant in range(VARIANTS):
                with self.subTest(name=name, variant=variant):
                    self.assertEqual(pixel(name, variant, 0, 0), (0, 0, 0, 0))
                    self.assertEqual(pixel(name, variant, 95, 47), (0, 0, 0, 0))
                    self.assertEqual(pixel(name, variant, 48, 24)[3], 255)
                    center = pixel(name, variant, 48, 24)[:3]
                    neighborhood = {pixel(name, variant, x, y)[:3]
                                    for x in (31, 40, 48, 56, 62)
                                    for y in (16, 24, 30)}
                    self.assertIn(center, neighborhood)
                    self.assertGreater(len(neighborhood), 4)

    def test_adjacent_variants_share_identical_painted_edges(self):
        for name in MATERIALS:
            for y in range(TILE_HEIGHT):
                for x in range(TILE_WIDTH):
                    distance = (abs(x+.5-48)/48 + abs(y+.5-24)/24)
                    if .90 <= distance < 1:
                        left, right = pixel(name, 0, x, y), pixel(name, 1, x, y)
                        self.assertEqual(left, right)
                        self.assertEqual(left, (*PIGMENTS[name], 255))

    def test_no_random_state_or_invalid_colors(self):
        for bad in ('lava', '', 'purple'):
            with self.assertRaises(ValueError):
                pixel(bad, 0, 48, 24)
        for bad in (-1, 2, True):
            with self.assertRaises(ValueError):
                pixel('grass', bad, 48, 24)
        for x, y in ((-1, 0), (96, 0), (0, 48)):
            with self.assertRaises(ValueError):
                pixel('grass', 0, x, y)

    def test_export_roundtrip_has_same_bytes(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'terrain_watercolor.png'
            report = write_watercolor_atlas(out)
            self.assertEqual(out.read_bytes(), watercolor_atlas_png())
            self.assertEqual(report['sha256'], watercolor_atlas_sha256())
            self.assertEqual(report['width'], 1536)
            self.assertEqual(report['height'], 48)


if __name__ == '__main__':
    unittest.main()
