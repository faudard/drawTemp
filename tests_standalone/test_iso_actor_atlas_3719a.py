"""3.7.19A: direction, safety and integrity of original chibi actor sprites."""
import binascii
import struct
from pathlib import Path
from types import SimpleNamespace
import unittest

from sporebound.iso_actor_atlas import (
    ACTOR_DIRECTIONS, ACTOR_FRAME_SIZE, ACTOR_FRAMES, ACTOR_STYLES,
    DEFAULT_ACTOR_ATLAS, IsoActorAtlas, actor_direction, actor_frame,
    actor_style)
from sporebound.visual_motion import ActorPose


def actor(**kw):
    return SimpleNamespace(**kw)


class IsoActorAtlasTests(unittest.TestCase):
    def test_real_png_crc_dimensions_palette_and_24_distinct_frames(self):
        data = DEFAULT_ACTOR_ATLAS.read_bytes()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        pos, chunks = 8, {}
        while pos < len(data):
            n = struct.unpack_from('>I', data, pos)[0]
            kind = data[pos+4:pos+8]
            payload = data[pos+8:pos+8+n]
            crc = struct.unpack_from('>I', data, pos+8+n)[0]
            self.assertEqual(binascii.crc32(kind + payload) & 0xffffffff, crc)
            chunks[kind] = payload
            pos += n + 12
        self.assertEqual(pos, len(data))
        w, h, bitdepth, mode, *_ = struct.unpack('>IIBBBBB', chunks[b'IHDR'])
        self.assertEqual((w, h, bitdepth, mode), (512, 192, 8, 3))
        self.assertEqual(ACTOR_FRAME_SIZE, (64, 64))
        self.assertEqual((len(ACTOR_STYLES), len(ACTOR_DIRECTIONS),
                          ACTOR_FRAMES), (3, 4, 2))
        self.assertEqual(chunks[b'tRNS'][0], 0)
        self.assertTrue(all(v == 255 for v in chunks[b'tRNS'][1:]))
        import zlib
        rows = zlib.decompress(chunks[b'IDAT'])
        stride = w + 1
        self.assertEqual(len(rows), h * stride)
        frames = []
        for archetype in range(3):
            for direction in range(4):
                for motion in range(2):
                    cells = []
                    for y in range(archetype*64, (archetype+1)*64):
                        self.assertEqual(rows[y*stride], 0)
                        x = (direction*2+motion)*64
                        cells.extend(rows[y*stride+1+x:y*stride+1+x+64])
                    self.assertGreater(sum(v != 0 for v in cells), 400)
                    frames.append(bytes(cells))
        self.assertGreater(len(set(frames)), 12)

    def test_roles_and_orientation_are_presentation_only(self):
        self.assertEqual(actor_style(actor(team='player')), 'hero')
        self.assertEqual(actor_style(actor(team='enemy')), 'guard')
        self.assertEqual(actor_style(actor(team='neutral')), 'archer')
        self.assertEqual(actor_style(actor(team='enemy', weapon='bow')), 'archer')
        self.assertEqual(actor_style(actor(team='player', archetype='ranger')),
                         'archer')
        orientations = {(0, 1): 'south', (0, -1): 'north',
                        (1, 0): 'east', (-1, 0): 'west'}
        for facing, name in orientations.items():
            with self.subTest(facing=facing):
                self.assertEqual(actor_direction(actor(facing=facing)), name)
        self.assertEqual(actor_direction(actor(facing=(True, 0))), 'south')
        pose = ActorPose(1.25, 2.0, 'move', 'north')
        self.assertEqual(actor_direction(actor(facing=(0, 1)), pose), 'north')
        self.assertEqual(actor_frame(pose), 1)
        self.assertEqual(actor_frame(), 0)

    def test_invalid_and_missing_sprites_fall_back_without_importing_tk(self):
        import sys
        before = 'tkinter' in sys.modules
        atlas = IsoActorAtlas(None, path=Path('/missing/chibi.png'))
        for args in [('unknown', 'south', 0, 54),
                     ('hero', 'diagonal', 0, 54),
                     ('guard', 'north', True, 54),
                     ('archer', 'south', 2, 54),
                     ('hero', 'south', 0, 0)]:
            self.assertIsNone(atlas.sprite(*args))
        self.assertEqual('tkinter' in sys.modules, before)
        atlas.clear_cache()
        self.assertIsNone(atlas._source)


if __name__ == '__main__':
    unittest.main()
