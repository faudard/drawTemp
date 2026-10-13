"""Visual fidelity gates: atlas alpha, action poses and scene depth, headless."""
import binascii
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.iso_actor_atlas import (
    DEFAULT_ACTOR_ATLAS, DEFAULT_JEANNE_ATLAS, actor_action)
from sporebound.iso_building_atlas import DEFAULT_BUILDING_ATLAS
from sporebound.iso_depth import depth_order
from sporebound.iso_fortification_atlas import DEFAULT_FORTIFICATION_ATLAS
from sporebound.iso_map import DEFAULT_TERRAIN_ATLAS, render_isometric
from sporebound.iso_object_atlas import DEFAULT_OBJECT_ATLAS
from sporebound.iso_props import DEFAULT_PROP_ATLAS
from sporebound.iso_structures import place_structure
from sporebound.model import Content
from sporebound.visual_motion import ActorPose


ATLAS_SPECS = (
    (DEFAULT_TERRAIN_ATLAS, (1536, 48)),
    (DEFAULT_PROP_ATLAS, (1152, 128)),
    (DEFAULT_OBJECT_ATLAS, (336, 64)),
    (DEFAULT_BUILDING_ATLAS, (2100, 220)),
    (DEFAULT_FORTIFICATION_ATLAS, (2700, 250)),
    (DEFAULT_ACTOR_ATLAS, (512, 192)),
    (DEFAULT_JEANNE_ATLAS, (256, 512)),
)


class EvidenceCanvas:
    def __init__(self):
        self.commands = []

    def __getattr__(self, name):
        if name.startswith('create_') or name in ('configure', 'delete', 'tag_raise'):
            def record(*args, **kwargs):
                self.commands.append((name, args, kwargs))
                return len(self.commands)
            return record
        raise AttributeError(name)


class VisualFidelityArtTests(unittest.TestCase):
    def test_atlases_have_verified_png_chunks_and_actual_transparency(self):
        for path, expected in ATLAS_SPECS:
            with self.subTest(path=path.name):
                raw = path.read_bytes()
                self.assertEqual(raw[:8], bytes((137, 80, 78, 71, 13, 10, 26, 10)))
                cursor, kinds = 8, []
                width = height = color_type = None
                while cursor < len(raw):
                    self.assertGreaterEqual(len(raw) - cursor, 12)
                    size = struct.unpack_from('>I', raw, cursor)[0]
                    tag = raw[cursor+4:cursor+8]
                    end = cursor + size + 12
                    self.assertLessEqual(end, len(raw))
                    payload = raw[cursor+8:cursor+8+size]
                    crc = struct.unpack_from('>I', raw, end-4)[0]
                    self.assertEqual(binascii.crc32(tag + payload) & 0xffffffff, crc)
                    kinds.append(tag)
                    if tag == b'IHDR':
                        width, height, depth, color_type, *_ = struct.unpack(
                            '>IIBBBBB', payload)
                        self.assertEqual(depth, 8)
                    cursor = end
                    if tag == b'IEND':
                        break
                self.assertEqual(cursor, len(raw))
                self.assertEqual((width, height), expected)
                self.assertIn(b'IDAT', kinds)
                self.assertEqual(kinds[-1], b'IEND')
                self.assertTrue(color_type == 6 or
                                (color_type == 3 and b'tRNS' in kinds),
                                f'{path} has no transparency')

    def test_pose_action_whitelist_keeps_headless_and_legacy_fallback(self):
        for action in ('idle', 'move', 'attack', 'hit', 'defeat'):
            self.assertEqual(actor_action(ActorPose(2, 3, action, 'east')), action)
        self.assertEqual(actor_action(ActorPose(2, 3, 'unknown', 'east')), 'idle')
        self.assertEqual(actor_action(None), 'idle')

    def test_scattered_props_objects_roofs_and_units_share_foot_depth(self):
        house = SimpleNamespace(cells=frozenset(((3, 3), (4, 3))))
        rear = SimpleNamespace(id='rear', pos=(1, 1))
        front = SimpleNamespace(id='front', pos=(9, 9))
        ordered = depth_order(
            (house,), (rear, front), objects=(
                {'id': 'chest_behind', 'pos': (3, 2)},
                {'id': 'chest_front', 'pos': (10, 2)}),
            props=((2, 2), (9, 3)))
        self.assertEqual(ordered, (
            'iso_actor_unit_0', 'iso_decor_cell_2_2',
            'iso_object_chest_behind', 'architecture_instance_0',
            'iso_decor_cell_9_3', 'iso_object_chest_front',
            'iso_actor_unit_1'))
        tied = depth_order(
            (SimpleNamespace(cells=((3, 3),)),),
            (SimpleNamespace(pos=(3, 3)),),
            objects=({'id': 'chest', 'pos': (3, 3)},), props=((3, 3),))
        self.assertEqual(tied, (
            'iso_decor_cell_3_3', 'iso_object_chest',
            'architecture_instance_0', 'iso_actor_unit_0'))

    def test_vector_fallback_and_object_primitives_receive_depth_tags(self):
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'fidelity_gate', 'Fidelity', 12, 12)
        data = place_structure(data, 'fidelity_gate', 'Maison', (3, 3))
        row = next(m for m in data['missions'] if m['id'] == 'fidelity_gate')
        row['board']['tiles'].append({'pos': [9, 8], 'feature': 'tree'})
        row['objects'] = [{'id': 'chest_gate', 'kind': 'chest', 'pos': [9, 7]}]
        mission = Content.from_dict(data).missions['fidelity_gate']
        canvas = EvidenceCanvas()
        render_isometric(
            canvas, mission.board, mission, mission.units, cell_size=54,
            layers={'Terrain': True, 'Décors': True, 'Objets': True,
                    'Bâtiments': True, 'Toitures': True, 'Unités': True},
            selected_cell=(0, 0), selected_tiles=())
        self.assertTrue(any('iso_decor_cell_9_8' in kw.get('tags', ())
                            for name, args, kw in canvas.commands
                            if name.startswith('create_')))
        self.assertTrue(any('iso_object_chest_gate' in kw.get('tags', ())
                            for name, args, kw in canvas.commands
                            if name.startswith('create_')))
        raised = [args[0] for name, args, kw in canvas.commands
                  if name == 'tag_raise']
        self.assertIn('iso_decor_cell_9_8', raised)
        self.assertIn('iso_object_chest_gate', raised)
        self.assertIn('architecture_instance_0', raised)
        self.assertEqual(raised[-1], 'selection')


if __name__ == '__main__':
    unittest.main()
