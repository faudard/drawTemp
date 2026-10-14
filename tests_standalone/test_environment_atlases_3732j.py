"""3.7.32J — exact PNG animation contracts without Pillow, Tk or the engine."""
import hashlib
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
import zlib

from sporebound.environment_atlas import (
    FRAME_SIZE, FRAME_COUNT, KINDS, PIVOTS, environment_strip_png,
    export_atlases, frame_rgba,
)
from sporebound.model import Board, Tile
from sporebound.terrain_ambient import (
    ambient_kind, sprite_origin, sprite_phase, sprite_tag,
    TerrainAmbientAnimator,
)


class AnimatedEnvironmentAtlasTests(unittest.TestCase):
    def test_complete_true_rgba_sprite_sheets_with_crc_and_alpha(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                png = environment_strip_png(kind)
                self.assertIs(png, environment_strip_png(kind))
                self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
                off = 8
                chunks = []
                header = None
                while off < len(png):
                    length = struct.unpack('>I', png[off:off+4])[0]
                    marker = png[off+4:off+8]
                    data = png[off+8:off+8+length]
                    crc = struct.unpack('>I', png[off+8+length:off+12+length])[0]
                    self.assertEqual(zlib.crc32(marker+data) & 0xffffffff, crc)
                    if marker == b'IHDR':
                        header = struct.unpack('>IIBBBBB', data)
                    if marker == b'IDAT':
                        chunks.append(data)
                    off += 12+length
                self.assertEqual(off, len(png))
                self.assertEqual(header, (512, 64, 8, 6, 0, 0, 0))
                raw = zlib.decompress(b''.join(chunks))
                self.assertEqual(len(raw), 64 * (512*4+1))
                self.assertTrue(all(raw[y*(512*4+1)] == 0 for y in range(64)))
                self.assertLess(len(png), 200000)

    def test_eight_distinct_painted_frames_and_fixed_roots(self):
        self.assertEqual(len(KINDS), 4)
        for kind in KINDS:
            with self.subTest(kind=kind):
                frames = [frame_rgba(kind, step) for step in range(FRAME_COUNT)]
                # A looping hand-painted cycle legitimately repeats the
                # neutral/rest poses; it must still include moving frames.
                self.assertGreaterEqual(len(set(frames)), 4)
                self.assertTrue(all(len(f) == 64*64*4 for f in frames))
                self.assertTrue(all(f[:4] == bytes(4) for f in frames))
                self.assertTrue(all(f[-4:] == bytes(4) for f in frames))
                self.assertTrue(all(any(f[i] > 0 for i in range(3, len(f), 4))
                                    for f in frames))
                self.assertEqual(len(PIVOTS[kind]), 2)
                for p in PIVOTS[kind]:
                    self.assertGreaterEqual(p, 0)
                    self.assertLess(p, FRAME_SIZE)
        # The anchored grass root must never drift even if tips sway.
        root = (53*64 + 32)*4+3
        self.assertTrue(all(frame_rgba('grass', i)[root] > 0
                            for i in range(FRAME_COUNT)))

    def test_manifest_and_pngs_match_bytes_exactly(self):
        with TemporaryDirectory() as temp:
            first = export_atlases(temp)
            second = export_atlases(temp)
            self.assertEqual(first, second)
            self.assertEqual(first['frames'], FRAME_COUNT)
            self.assertEqual(first['frame_duration_ms'], 125)
            for kind, data in first['materials'].items():
                png = (Path(temp)/data['file']).read_bytes()
                self.assertEqual(png, environment_strip_png(kind))
                self.assertEqual(hashlib.sha256(png).hexdigest(), data['sha256'])
                self.assertEqual(data['pivot'], list(PIVOTS[kind]))
            self.assertEqual(
                json.loads((Path(temp)/'manifest.json').read_text(encoding='utf-8')),
                first)

    def test_invalid_frames_never_leak_to_renderer(self):
        for kind, frame in (('lava', 0), ('grass', 8), ('water', -1),
                            ('reeds', True), ('tree', 3)):
            with self.subTest(kind=kind, frame=frame), self.assertRaises(ValueError):
                frame_rgba(kind, frame)
        with self.assertRaises(ValueError):
            environment_strip_png('unknown')

    def test_sprite_selection_pivots_and_phase_depend_only_on_view_data(self):
        board = Board(16, 16)
        board.tiles[(8, 8)] = Tile(feature='reeds')
        board.tiles[(9, 8)] = Tile(surface='water')
        self.assertEqual(ambient_kind(board, (8, 8)), 'reeds')
        anchor = sprite_origin(board, (8, 8), (200, 200), 54)
        self.assertIsNotNone(anchor)
        self.assertEqual(sprite_tag('reeds', (8, 8)),
                         'iso_env_frame_reeds_8_8')
        self.assertNotEqual(sprite_phase('reeds', (8, 8), 0),
                            sprite_phase('reeds', (8, 8), 125))
        self.assertEqual(sprite_phase('reeds', (8, 8), 0),
                         sprite_phase('reeds', (8, 8), 1000))
        self.assertEqual(anchor, sprite_origin(board, (8, 8), (200, 200), 54))
        self.assertEqual(sprite_origin(board, (8, 8), (200, 200), 24),
                         sprite_origin(board, (8, 8), (200, 200), 24))
        self.assertIsNone(sprite_origin(board, (99, 99), (0, 0), 54))
        with self.assertRaises(ValueError):
            sprite_phase('grass', (2, 2), -1)

    def test_density_stays_bounded_on_128_squared(self):
        board = Board(128, 128)
        animated = sum(ambient_kind(board, cell) is not None for cell in board.cells())
        self.assertGreater(animated, 0)
        self.assertLess(animated, 512)


class FakeCanvas:
    def __init__(self):
        self.photos = {9: 'frame0'}
        self.coords_map = {9: (100, 100)}

    def find_withtag(self, tag):
        return (9,) if tag == 'iso_ambient' else ()

    def type(self, item):
        return 'image'

    def gettags(self, item):
        return ('iso_ambient', 'iso_env_frame_grass_3_4', 'iso_tile_3_4')

    def coords(self, item, *new):
        if new:
            self.coords_map[item] = tuple(new)
        return self.coords_map[item]

    def itemcget(self, item, option):
        return self.photos[item]

    def itemconfigure(self, item, **kwargs):
        self.photos[item] = kwargs['image']


class FakeAtlas:
    def frame(self, kind, size, phase):
        return (kind, size, phase)


class AmbientImageContractTests(unittest.TestCase):
    def test_capture_swap_and_restore_only_image_handles(self):
        canvas = FakeCanvas()
        animator = TerrainAmbientAnimator()
        self.assertEqual(animator.capture(canvas), 1)
        self.assertTrue(animator.active)
        self.assertEqual(animator.tick(canvas, 0, atlas=FakeAtlas(), cell_size=54), 1)
        self.assertIsInstance(canvas.photos[9], tuple)
        self.assertEqual(canvas.coords(9), (100, 100))
        self.assertEqual(animator.tick(canvas, 1, atlas=FakeAtlas(), cell_size=54), 0)
        animator.restore(canvas)
        self.assertEqual(canvas.photos[9], 'frame0')
        self.assertEqual(animator.capture(canvas), 1)
        animator.clear()
        self.assertFalse(animator.active)


if __name__ == '__main__':
    unittest.main()
