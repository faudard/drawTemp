"""3.7.15 visual-only fortification atlas, rotation and legacy schema gates."""
import binascii
import struct
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest
import zlib

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_architecture import (
    SCENERY_NAMES, architecture_instances, architecture_outline, draw_architecture)
from sporebound.iso_fortification_atlas import (
    FORTIFICATION_FRAMES, FORTIFICATION_FRAME_SIZE,
    FORTIFICATION_SOURCE_CELL_SIZE, FORTIFICATION_ROOF_NORTH,
    DEFAULT_FORTIFICATION_ATLAS, IsoFortificationAtlas,
    fortification_sprite_top_left)
from sporebound.iso_map import IsoGeometry
from sporebound.iso_structures import place_structure
from sporebound.model import Content


class CanvasRecorder:
    def __init__(self):
        self.calls = []

    def __getattr__(self, method):
        if method.startswith(('create_', 'tag_')):
            def record(*args, **kwargs):
                self.calls.append((method, args, kwargs))
                return len(self.calls)
            return record
        raise AttributeError(method)

    def tagged(self, name):
        return [row for row in self.calls if name in row[2].get('tags', ())]


class AtlasStub:
    def __init__(self, available=True):
        self.available = available
        self.calls = []

    def sprite(self, name, turns, cell_size):
        self.calls.append((name, turns, cell_size))
        return object() if self.available else None


class FortificationAtlasTests(unittest.TestCase):
    def setUp(self):
        doc = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                'fortification', 'Fortifications', 12, 12)
        self.mid = 'fortification'
        self.doc = Document(Content.from_dict(doc))

    def place(self, name, turns=0):
        self.doc.replace(place_structure(self.doc.data, self.mid, name,
                                         (3, 3), turns))
        board = Content.from_dict(self.doc.data).missions[self.mid].board
        matches = [x for x in architecture_instances(board) if x.name == name]
        self.assertEqual(len(matches), 1)
        return board, matches[0]

    def test_real_png_frames_have_crc_alpha_and_nonempty_art(self):
        data = DEFAULT_FORTIFICATION_ATLAS.read_bytes()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        offset, chunks = 8, {}
        while offset < len(data):
            count = struct.unpack_from('>I', data, offset)[0]
            name = data[offset+4:offset+8]
            value = data[offset+8:offset+8+count]
            crc = struct.unpack_from('>I', data, offset+8+count)[0]
            self.assertEqual(binascii.crc32(name+value)&0xffffffff, crc)
            chunks.setdefault(name, []).append(value)
            offset += count+12
        self.assertEqual(offset, len(data))
        width, height, bits, mode, *_ = struct.unpack(
            '>IIBBBBB', chunks[b'IHDR'][0])
        fw, fh = FORTIFICATION_FRAME_SIZE
        self.assertEqual((width, height, bits, mode),
                         (fw*len(FORTIFICATION_FRAMES), fh, 8, 3))
        palette = chunks[b'PLTE'][0]
        alpha = chunks[b'tRNS'][0]
        self.assertGreaterEqual(len(palette), 16*3)
        self.assertEqual(alpha[0], 0)
        # The ground and river are already rendered by IsoTerrainAtlas.
        # An earlier art pack baked an extra river wedge into both bridge
        # sprites and large ellipses under every fortification sprite.
        # Those palette indices must stay transparent so Atlas sprites
        # never paint over neighbouring terrain or beyond the map edge.
        self.assertEqual(alpha[1], 0, 'Baked detached ground shadows')
        self.assertEqual(tuple(alpha[idx] for idx in (7, 8, 9)), (0, 0, 0),
                         'Baked bridge water would overlap the actual river')
        self.assertEqual(tuple(alpha[idx] for idx in (2, 3, 4, 5, 10, 11)),
                         (255,) * 6, 'Keep stone and timber opaque')
        raw = zlib.decompress(b''.join(chunks[b'IDAT']))
        stride = width+1
        self.assertEqual(len(raw), stride*height)
        for frame in range(len(FORTIFICATION_FRAMES)):
            seen = 0
            for y in range(0, fh, 3):
                line = raw[y*stride:(y+1)*stride]
                self.assertEqual(line[0], 0)  # PNG filter None
                seen += sum(idx != 0 for idx in
                            line[frame*fw+1:(frame+1)*fw+1:3])
            self.assertGreater(seen, 150)

    def test_all_six_visual_stamps_are_detected_and_undoable(self):
        self.assertEqual(SCENERY_NAMES, ('Rempart', 'Escalier', 'Pont'))
        for name in SCENERY_NAMES:
            for turns in range(4):
                with self.subTest(name=name, turns=turns):
                    self.setUp()
                    original = self.doc.data
                    original_snapshot = __import__('copy').deepcopy(original)
                    board, match = self.place(name, turns)
                    clip = __import__('sporebound.iso_structures',
                                      fromlist=['structure_template']).structure_template(
                                          name, turns)
                    self.assertEqual((match.width, match.height),
                                     (clip.width, clip.height))
                    self.assertEqual(len(match.cells), len(clip.offsets))
                    self.assertEqual(match.anchor, (3, 3))
                    self.doc.undo()
                    self.assertEqual(self.doc.data, original_snapshot)
                    self.doc.redo()
                    self.assertEqual(len(architecture_instances(
                        Content.from_dict(self.doc.data).missions[self.mid].board)), 1)

    def test_save_reload_and_nonexistent_legacy_roofs(self):
        board, match = self.place('Pont')
        self.assertEqual(len(architecture_instances(board)), 1)
        with TemporaryDirectory() as folder:
            path = Path(folder)/'no_schema_change.json'
            self.doc.save(path)
            loaded = Content.load(path).missions[self.mid].board
            self.assertEqual(architecture_instances(loaded), (match,))
        self.doc.undo()
        self.assertEqual(architecture_instances(
            Content.from_dict(self.doc.data).missions[self.mid].board), ())

    def test_sprite_alignment_at_zoom_and_visual_cutaway(self):
        for name in SCENERY_NAMES:
            self.setUp()
            board, instance = self.place(name)
            for zoom in (24, 54, 96):
                geo = IsoGeometry(board, zoom)
                origin = fortification_sprite_top_left(geo, instance)
                wall = 2 if name == 'Rempart' else 0
                north = architecture_outline(geo, instance, wall_level=wall)[0][0]
                scale = zoom/FORTIFICATION_SOURCE_CELL_SIZE
                self.assertAlmostEqual(origin[0]+FORTIFICATION_ROOF_NORTH[0]*scale,
                                       north[0])
                self.assertAlmostEqual(origin[1]+FORTIFICATION_ROOF_NORTH[1]*scale,
                                       north[1])
            canvas = CanvasRecorder()
            atlas = AtlasStub()
            draw_architecture(canvas, IsoGeometry(board, 54), board, (), (0, 0),
                              {'Bâtiments': True, 'Toitures': False},
                              scenery_atlas=atlas)
            self.assertEqual(len(canvas.tagged('architecture_scenery_sprite')), 1)
            self.assertEqual(len(atlas.calls), 1)
            self.assertEqual(canvas.calls[-1][1], ('selection',))
            cutaway = CanvasRecorder()
            draw_architecture(cutaway, IsoGeometry(board, 54), board, (), (3, 3),
                              {'Bâtiments': True, 'Toitures': True},
                              scenery_atlas=AtlasStub())
            self.assertFalse(cutaway.tagged('architecture_scenery_sprite'))
            fallback = CanvasRecorder()
            draw_architecture(fallback, IsoGeometry(board, 54), board, (), (0, 0),
                              {'Bâtiments': True, 'Toitures': False},
                              scenery_atlas=AtlasStub(False))
            self.assertFalse(fallback.tagged('architecture_scenery_sprite'))

    def test_invalid_lookup_does_not_import_tk(self):
        atlas = IsoFortificationAtlas(None, path=Path('/invalid/path.png'))
        for args in [('House', 0, 54), ('Pont', True, 54),
                     ('Rempart', '90', 54), ('Pont', 0, 0)]:
            self.assertIsNone(atlas.sprite(*args))


if __name__ == '__main__':
    unittest.main()
