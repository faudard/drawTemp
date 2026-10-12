"""3.7.14 building art: PNG evidence, headless geometry and Tk fallback."""
import binascii
from pathlib import Path
import struct
import unittest
import zlib

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_architecture import architecture_instances, draw_architecture
from sporebound.iso_building_atlas import (
    BUILDING_FRAME_SIZE, BUILDING_FRAMES, BUILDING_ROOF_NORTH,
    BUILDING_SOURCE_CELL_SIZE, DEFAULT_BUILDING_ATLAS, IsoBuildingAtlas,
    building_sprite_top_left)
from sporebound.iso_map import IsoGeometry
from sporebound.iso_structures import place_structure
from sporebound.model import Content


class CanvasRecorder:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith(('create_', 'tag_')):
            def record(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return len(self.calls)
            return record
        raise AttributeError(name)

    def tagged(self, tag):
        return [call for call in self.calls
                if tag in call[2].get('tags', ())]


class AtlasStub:
    def __init__(self, available=True):
        self.available = available
        self.requests = []

    def sprite(self, name, turns, cell_size):
        self.requests.append((name, turns, cell_size))
        return object() if self.available else None


class IsoBuildingAtlasTests(unittest.TestCase):
    def setUp(self):
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'buildings', 'Building atlas', 12, 12)
        self.doc = Document(Content.from_dict(data))
        self.mid = 'buildings'

    def place(self, name='Maison', turns=0):
        self.doc.replace(place_structure(
            self.doc.data, self.mid, name, (3, 3), turns))
        board = Content.from_dict(self.doc.data).missions[self.mid].board
        instance = next(instance for instance in architecture_instances(board)
                        if instance.name == name)
        return board, instance

    def test_atlas_is_a_real_png_with_six_complete_transparent_frames(self):
        payload = DEFAULT_BUILDING_ATLAS.read_bytes()
        self.assertEqual(payload[:8], bytes((137, 80, 78, 71, 13, 10, 26, 10)))
        pos = 8
        chunks = {}
        while pos < len(payload):
            length = struct.unpack_from('>I', payload, pos)[0]
            kind = payload[pos+4:pos+8]
            data = payload[pos+8:pos+8+length]
            expected = struct.unpack_from('>I', payload, pos+8+length)[0]
            self.assertEqual(binascii.crc32(kind+data) & 0xffffffff, expected)
            chunks.setdefault(kind, []).append(data)
            pos += 12+length
        self.assertEqual(pos, len(payload))
        width, height, depth, color, _, _, _ = struct.unpack(
            '>IIBBBBB', chunks[b'IHDR'][0])
        fw, fh = BUILDING_FRAME_SIZE
        self.assertEqual((width, height, depth, color),
                         (fw*len(BUILDING_FRAMES), fh, 8, 3))
        self.assertEqual(len(chunks[b'PLTE'][0]), 16*3)
        self.assertEqual(chunks[b'tRNS'][0][0], 0)
        decoded = zlib.decompress(b''.join(chunks[b'IDAT']))
        self.assertEqual(len(decoded), height*(width+1))
        self.assertEqual(BUILDING_FRAMES[0], ('Maison', 0))
        self.assertEqual(BUILDING_FRAMES[-1], ('Ruines', 1))
        for frame in range(len(BUILDING_FRAMES)):
            # A playable sprite has visible art in every frame but the
            # padded top-left stays fully transparent.
            visible = 0
            for y in range(0, fh, 2):
                scan = decoded[y*(width+1): (y+1)*(width+1)]
                self.assertEqual(scan[0], 0)  # PNG filter None
                visible += sum(value != 0
                               for value in scan[1+frame*fw:1+(frame+1)*fw:2])
            self.assertGreater(visible, 250)
            self.assertEqual(decoded[0*(width+1)+1+frame*fw], 0)

    def test_geometry_aligns_the_roof_north_at_three_zoom_levels(self):
        board, building = self.place()
        for cell_size in (24, 54, 96):
            geo = IsoGeometry(board, cell_size)
            origin = building_sprite_top_left(geo, building)
            north = __import__('sporebound.iso_architecture',
                               fromlist=['architecture_outline']).architecture_outline(
                                   geo, building)[0][0]
            scale = cell_size/BUILDING_SOURCE_CELL_SIZE
            self.assertAlmostEqual(origin[0]+BUILDING_ROOF_NORTH[0]*scale,
                                   north[0])
            self.assertAlmostEqual(origin[1]+BUILDING_ROOF_NORTH[1]*scale,
                                   north[1])

    def test_sprite_is_drawn_when_closed_and_vector_when_cutaway(self):
        board, building = self.place('Maison')
        geo = IsoGeometry(board, 54)
        atlas = AtlasStub()
        recorder = CanvasRecorder()
        draw_architecture(recorder, geo, board, (), (0, 0),
                          {'Bâtiments': True, 'Toitures': True},
                          atlas=atlas)
        self.assertEqual(len(recorder.tagged('architecture_sprite')), 1)
        self.assertEqual(atlas.requests, [('Maison', building.turns, 54)])
        self.assertEqual(len(recorder.tagged('architecture_roof')), 0)

        recorder = CanvasRecorder()
        draw_architecture(recorder, geo, board, (), (4, 4),
                          {'Bâtiments': True, 'Toitures': True}, atlas=atlas)
        self.assertEqual(len(recorder.tagged('architecture_sprite')), 0)
        self.assertGreater(len(recorder.tagged('architecture_cutaway')), 0)

        recorder = CanvasRecorder()
        fallback = AtlasStub(False)
        draw_architecture(recorder, geo, board, (), (0, 0),
                          {'Bâtiments': True, 'Toitures': True}, atlas=fallback)
        self.assertEqual(len(recorder.tagged('architecture_sprite')), 0)
        self.assertGreater(len(recorder.tagged('architecture_roof')), 0)

        recorder = CanvasRecorder()
        draw_architecture(recorder, geo, board, (), (0, 0),
                          {'Bâtiments': True, 'Toitures': False}, atlas=atlas)
        self.assertEqual(len(recorder.tagged('architecture_sprite')), 0)
        self.assertEqual(len(recorder.tagged('architecture_roof')), 0)

    def test_ruins_sprite_is_compatible_with_hidden_roofs(self):
        board, _ = self.place('Ruines')
        atlas = AtlasStub()
        recorder = CanvasRecorder()
        draw_architecture(recorder, IsoGeometry(board, 54),
                          board, (), (0, 0),
                          {'Bâtiments': True, 'Toitures': False}, atlas=atlas)
        self.assertEqual(len(recorder.tagged('architecture_sprite')), 1)

    def test_invalid_atlas_requests_short_circuit_without_tk(self):
        loader = IsoBuildingAtlas(None, path=Path('/missing/atlas.png'))
        self.assertIsNone(loader.sprite('???', 0, 54))
        self.assertIsNone(loader.sprite('Maison', 'bad', 54))
        self.assertIsNone(loader.sprite('Maison', True, 54))
        self.assertIsNone(loader.sprite('Maison', 0, 0))


if __name__ == '__main__':
    unittest.main()
