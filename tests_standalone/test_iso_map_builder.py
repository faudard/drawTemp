"""2.5D map authoring contracts: painting, stamps, projection and collision."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_map import IsoGeometry, _line_cells
from sporebound.map_authoring import copy_terrain, paste_terrain
from sporebound.map_transform import parse_stamp, stamp_document, transform_terrain
from sporebound.model import Content, RuleError


class IsometricMapAuthoringTests(unittest.TestCase):
    def setUp(self):
        base = Content.load(DEFAULT_CONTENT).to_dict()
        self.mid = 'isometric_sandbox'
        data = add_blank_mission(base, self.mid, 'Relief et rivière', 12, 12)
        self.doc = Document(Content.from_dict(data))

    def board(self):
        return Content.from_dict(self.doc.data).missions[self.mid].board

    def test_stacked_layers_and_absolute_height_survive_serialization(self):
        self.doc.paint_many(self.mid, [(4, 4)], 'surface:cobble')
        self.doc.paint_many(self.mid, [(4, 4)], 'feature:ruin')
        self.doc.paint_many(self.mid, [(4, 4)], 'height:3')
        tile = self.board().tile((4, 4))
        self.assertEqual((tile.surface, tile.feature, tile.height),
                         ('cobble', 'ruin', 3))
        self.doc.paint_many(self.mid, [(4, 4)], 'feature-erase')
        self.assertEqual(self.board().tile((4, 4)).surface, 'cobble')
        self.assertEqual(self.board().tile((4, 4)).height, 3)
        self.assertEqual(self.board().tile((4, 4)).feature, '')

    def test_river_blocks_walkers_bridge_reopens_crossing(self):
        self.doc.paint_many(self.mid, [(3, 3), (3, 4), (3, 5)],
                            'surface:water')
        self.assertTrue(self.board().tile((3, 4)).blocked)
        self.doc.paint_many(self.mid, [(3, 4)], 'surface:bridge')
        self.assertFalse(self.board().tile((3, 4)).blocked)
        self.assertTrue(self.board().tile((3, 5)).blocked)
        self.doc.undo()
        self.assertTrue(self.board().tile((3, 4)).blocked)
        self.doc.redo()
        self.assertEqual(self.board().tile((3, 4)).surface, 'bridge')

    def test_structure_collision_and_atomic_invalid_paint(self):
        self.doc.paint_many(self.mid, [(4, 4)], 'feature:stone_wall')
        self.assertTrue(self.board().tile((4, 4)).blocked)
        self.doc.paint_many(self.mid, [(4, 4)], 'feature-erase')
        self.assertFalse(self.board().tile((4, 4)).blocked)
        original = deepcopy(self.doc.data)
        player = next(u for u in Content.from_dict(original).missions[self.mid].units
                      if u.team == 'player')
        with self.assertRaises(RuleError):
            self.doc.paint_many(self.mid, [(6, 6), player.pos], 'surface:water')
        self.assertEqual(self.doc.data, original)
        for brush in ('surface:lava', 'feature:castle', 'height:100',
                      'height:-1', 'height:abc'):
            with self.subTest(brush=brush), self.assertRaises(RuleError):
                self.doc.paint_many(self.mid, [(4, 4)], brush)
            self.assertEqual(self.doc.data, original)

    def test_stamp_rotates_and_pastes_appearance_and_relief(self):
        self.doc.paint_many(self.mid, [(3, 3)], 'surface:water')
        self.doc.paint_many(self.mid, [(4, 3)], 'surface:bridge')
        self.doc.paint_many(self.mid, [(4, 3)], 'feature:lantern')
        self.doc.paint_many(self.mid, [(4, 3)], 'height:2')
        clip = copy_terrain(self.doc.data, self.mid, [(3, 3), (4, 3)])
        payload = stamp_document(clip, 'Rivière')
        turned = transform_terrain(parse_stamp(payload), 'rotate_cw')
        self.doc.replace(paste_terrain(self.doc.data, self.mid, turned, (7, 7)))
        b = self.board()
        self.assertEqual(b.tile((7, 7)).surface, 'water')
        self.assertEqual(b.tile((7, 8)).surface, 'bridge')
        self.assertEqual(b.tile((7, 8)).feature, 'lantern')
        self.assertEqual(b.tile((7, 8)).height, 2)

    def test_geometry_hit_testing_and_continuous_river_stroke(self):
        geo = IsoGeometry(self.board(), 54)
        for cell in ((2, 2), (4, 3), (8, 7)):
            self.assertEqual(geo.hit_test(*geo.center(cell)), cell)
        stroke = list(_line_cells((2, 3), (6, 3)))
        self.assertEqual(stroke, [(2, 3), (3, 3), (4, 3), (5, 3), (6, 3)])
        self.doc.paint_many(self.mid, stroke, 'surface:water')
        self.assertTrue(all(self.board().tile(c).blocked for c in stroke))
        self.doc.undo()
        self.assertTrue(all(self.board().tile(c).surface == 'grass' for c in stroke))

    def test_atlas_png_has_sixteen_valid_textured_frames(self):
        import struct
        import zlib
        from sporebound.iso_map import (ATLAS_MATERIALS, ATLAS_TILE_SIZE,
                                       ATLAS_VARIANTS, DEFAULT_TERRAIN_ATLAS)
        png = DEFAULT_TERRAIN_ATLAS.read_bytes()
        self.assertEqual(png[:8], b'\\x89PNG\\r\\n\\x1a\\n')
        length = struct.unpack('>I', png[8:12])[0]
        self.assertEqual(length, 13)
        width, height = struct.unpack('>II', png[16:24])
        self.assertEqual((width, height),
                         (len(ATLAS_MATERIALS)*ATLAS_VARIANTS*ATLAS_TILE_SIZE[0],
                          ATLAS_TILE_SIZE[1]))
        self.assertEqual(png[24:26], b'\\x08\\x06')  # RGBA
        chunks = []
        pos = 8
        while pos < len(png):
            size = struct.unpack('>I', png[pos:pos+4])[0]
            kind = png[pos+4:pos+8]
            data = png[pos+8:pos+8+size]
            import binascii
            checksum = struct.unpack('>I',png[pos+8+size:pos+12+size])[0]
            self.assertEqual(binascii.crc32(kind+data)&0xffffffff, checksum)
            if kind == b'IDAT':
                chunks.append(data)
            pos += size+12
        raw = zlib.decompress(b''.join(chunks))
        stride = width*4+1
        self.assertEqual(len(raw), stride*height)
        center_y = height // 2
        for index in range(len(ATLAS_MATERIALS)*ATLAS_VARIANTS):
            frame_x = index*ATLAS_TILE_SIZE[0]
            alpha = raw[center_y*stride+1+(frame_x+ATLAS_TILE_SIZE[0]//2)*4+3]
            self.assertGreater(alpha, 170)
            corner_alpha = raw[center_y*stride+1+frame_x*4+3]
            self.assertEqual(corner_alpha, 0)

    def test_bad_visual_tokens_rejected_by_content_validation(self):
        payload = deepcopy(self.doc.data)
        mission = next(m for m in payload['missions'] if m['id'] == self.mid)
        mission['board']['tiles'].append({'pos': [5, 5], 'surface': '???'})
        with self.assertRaises(RuleError):
            Content.from_dict(payload)


if __name__ == '__main__':
    unittest.main()
