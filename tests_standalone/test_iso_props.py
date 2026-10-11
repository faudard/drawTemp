"""Bundled PNG prop atlas and headless authoring contracts."""
from copy import deepcopy
import struct
import unittest
import zlib

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_map import FEATURES
from sporebound.iso_props import (PROP_NAMES, PROP_FRAME_SIZE,
                                 DEFAULT_PROP_ATLAS)
from sporebound.model import Content, RuleError


class IsoPropsTests(unittest.TestCase):
    def test_png_dimensions_checksums_and_alpha(self):
        png = DEFAULT_PROP_ATLAS.read_bytes()
        self.assertEqual(png[:8], bytes((137, 80, 78, 71, 13, 10, 26, 10)))
        self.assertEqual(struct.unpack('>II', png[16:24]),
                         (len(PROP_NAMES)*PROP_FRAME_SIZE[0], PROP_FRAME_SIZE[1]))
        self.assertEqual(png[24:26], bytes((8, 6)))
        import binascii
        cursor = 8
        compressed = []
        while cursor < len(png):
            length = struct.unpack('>I', png[cursor:cursor+4])[0]
            kind = png[cursor+4:cursor+8]
            payload = png[cursor+8:cursor+8+length]
            checksum = struct.unpack('>I', png[cursor+8+length:cursor+12+length])[0]
            self.assertEqual(binascii.crc32(kind + payload) & 0xffffffff,
                             checksum)
            if kind == b'IDAT':
                compressed.append(payload)
            cursor += length + 12
        raw = zlib.decompress(b''.join(compressed))
        width, height = len(PROP_NAMES)*PROP_FRAME_SIZE[0], PROP_FRAME_SIZE[1]
        stride = width*4+1
        self.assertEqual(len(raw), stride*height)
        self.assertTrue(all(raw[row*stride] == 0 for row in range(height)))
        for index, name in enumerate(PROP_NAMES):
            with self.subTest(sprite=name):
                x0 = index * PROP_FRAME_SIZE[0]
                # Corner must be transparent; the sprite's torso/base nonempty.
                self.assertEqual(raw[1 + x0*4 + 3], 0)
                self.assertGreater(max(raw[row*stride + 1 + (x0+x)*4+3]
                                       for row in range(20, 117)
                                       for x in range(15, 80)), 200)

    def test_every_prop_has_valid_tile_id_and_survives_copy(self):
        self.assertTrue(set(PROP_NAMES) <= FEATURES)
        base = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'art_sandbox', 'Arche', 12, 12)
        doc = Document(Content.from_dict(base))
        for name in PROP_NAMES:
            with self.subTest(prop=name):
                doc.paint_many('art_sandbox', [(4, 4)], 'feature:'+name)
                target = Content.from_dict(doc.data).missions['art_sandbox'].board
                self.assertEqual(target.tile((4, 4)).feature, name)
        before = deepcopy(doc.data)
        with self.assertRaises(RuleError):
            doc.paint_many('art_sandbox', [(5, 5)], 'feature:unknown')
        self.assertEqual(doc.data, before)

    def test_prop_loader_is_headless_on_import(self):
        # Importing the module must not instantiate Tk or require a display.
        from sporebound.iso_props import IsoPropAtlas
        self.assertIsNone(IsoPropAtlas(None, '/missing.png').sprite('other', 54))
        self.assertIsNone(IsoPropAtlas(None, '/missing.png').sprite('', 54))


if __name__ == '__main__':
    unittest.main()
