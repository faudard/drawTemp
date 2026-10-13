"""Portable group prefabs: cross-mission reuse, library and atomic authoring."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_object
from sporebound.editor import Document
from sporebound.editor_architecture import EditingContext, GroupPrefabPlaceCommand
from sporebound.editor_groups import create_editor_group
from sporebound.group_prefabs import (
    capture_group_prefab, place_group_prefab, save_group_prefab,
    load_group_prefab, list_group_prefabs, prefab_display_cells,
    prefab_file_slug)
from sporebound.iso_structures import place_structure
from sporebound.model import Content, RuleError


class GroupPrefabsTests(unittest.TestCase):
    SRC = 'prefab_src'
    DST = 'prefab_dst'

    def setUp(self):
        data = Content.load(DEFAULT_CONTENT).to_dict()
        data = add_blank_mission(data, self.SRC, 'Prefab source', 24, 24)
        self.data = add_blank_mission(data, self.DST, 'Prefab destination', 24, 24)

    def mission(self, data, mid):
        return next(m for m in data['missions'] if m['id'] == mid)

    def groups(self, data, mid):
        return self.mission(data, mid).get('editor_groups', [])

    def test_export_import_nested_linked_objects_and_terrain(self):
        doc = Document(Content.from_dict(self.data))
        doc.paint_many(self.SRC, ((4, 4),), 'feature:tree')
        data = add_object(doc.data, self.SRC, 'doorA', 'door', (6, 4))
        data = add_object(data, self.SRC, 'leverA', 'switch', (7, 4),
                          link='doorA')
        data = create_editor_group(data, self.SRC, 'Cour',
                                   cells=((4, 4), (6, 4)))
        data = create_editor_group(data, self.SRC, 'Mécanismes',
                                   parent='group_1', cells=((7, 4),))
        original = deepcopy(data)
        prefab = capture_group_prefab(data, self.SRC,
                                      ('group_1', 'group_2'), 'Place fortifiée')
        self.assertEqual(prefab['size'], [4, 1])
        self.assertEqual(prefab['groups'][1]['parent'], 'group_1')
        self.assertEqual(prefab['groups'][0]['cells'], [[0, 0], [2, 0]])
        with TemporaryDirectory() as folder:
            path = Path(folder) / prefab_file_slug(prefab['name'])
            save_group_prefab(prefab, path)
            self.assertEqual(list_group_prefabs(folder), (path,))
            self.assertEqual(load_group_prefab(path), prefab)
            with self.assertRaises(RuleError):
                save_group_prefab(prefab, path)
        imported = place_group_prefab(data, self.DST, prefab, (12, 12))
        self.assertEqual(imported == original, False)
        self.assertEqual(data, original)
        groups = self.groups(imported, self.DST)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[1]['parent'], groups[0]['id'])
        self.assertEqual(groups[0]['cells'], [[12, 12], [14, 12]])
        self.assertEqual(groups[1]['cells'], [[15, 12]])
        self.assertEqual(Content.from_dict(imported).missions[self.DST]
                         .board.tile((12, 12)).feature, 'tree')
        objs = self.mission(imported, self.DST)['objects']
        lever = next(o for o in objs if o['kind'] == 'switch')
        door = next(o for o in objs if o['kind'] == 'door')
        self.assertEqual(lever['link'], door['id'])
        self.assertEqual(tuple(door['pos']), (14, 12))

    def test_import_same_prefab_twice_preview_and_undo(self):
        raw = create_editor_group(self.data, self.SRC, 'Jardin',
                                  cells=((4, 4),))
        prefab = capture_group_prefab(raw, self.SRC, ('group_1',), 'Jardin')
        doc = Document(Content.from_dict(raw))
        ctx = EditingContext(doc, lambda: self.DST)
        baseline = deepcopy(doc.data)
        prepared = ctx.preview(GroupPrefabPlaceCommand(prefab, (11, 11)))
        self.assertEqual(doc.data, baseline)
        ctx.apply(prepared)
        once = deepcopy(doc.data)
        doc.replace(place_group_prefab(doc.data, self.DST, prefab, (14, 14)))
        self.assertEqual(len(self.groups(doc.data, self.DST)), 2)
        ids = [g['id'] for g in self.groups(doc.data, self.DST)]
        self.assertNotEqual(ids[0], ids[1])
        doc.undo()
        self.assertEqual(doc.data, once)
        doc.undo()
        self.assertEqual(doc.data, baseline)
        doc.redo()
        self.assertEqual(doc.data, once)

    def test_tower_interior_connector_and_actor(self):
        from sporebound.interior_levels import add_interior_floor
        from sporebound.level_navigation import add_level_link, place_unit_on_level
        data = place_structure(self.data, self.SRC, 'Tour', (7, 7))
        sid = self.mission(data, self.SRC)['structures'][0]['id']
        data = add_interior_floor(data, self.SRC, sid, 1)
        data = add_level_link(data, self.SRC, (0, 8, 9), (1, 8, 8))
        uid = self.mission(data, self.SRC)['units'][0]['id']
        data = place_unit_on_level(data, self.SRC, uid, 1, (8, 8))
        data = create_editor_group(data, self.SRC, 'Tour gardée',
                                   cells=[(x, y) for y in range(7, 10)
                                          for x in range(7, 10)])
        prefab = capture_group_prefab(data, self.SRC,
                                      ('group_1',), 'Tour')
        self.assertEqual(len(prefab['structures']), 1)
        self.assertEqual(len(prefab['level_links']), 1)
        imported = place_group_prefab(data, self.DST, prefab, (12, 6))
        m = self.mission(imported, self.DST)
        self.assertEqual(m['structures'][0]['anchor'], [12, 6])
        self.assertEqual(m['interior_floors'][0]['structure_id'],
                         m['structures'][0]['id'])
        self.assertEqual(m['level_links'][0]['from'], [0, 13, 8])
        self.assertEqual(m['level_links'][0]['to'], [1, 13, 7])
        new_uid = self.groups(imported, self.DST)[0]['unit_ids'][0]
        self.assertEqual(m['unit_levels'][new_uid], 1)
        Content.from_dict(imported)

    def test_collision_and_bad_anchor_leave_document_unchanged(self):
        src = create_editor_group(self.data, self.SRC, 'Arbre',
                                  cells=((4, 4),))
        prefab = capture_group_prefab(src, self.SRC, ('group_1',), 'Arbre')
        doc = Document(Content.from_dict(src))
        doc.paint_many(self.DST, ((12, 12),), 'feature:boulder')
        original = deepcopy(doc.data)
        history = len(doc.undo_stack)
        for anchor in ((12, 12), (-1, 0), (24, 24), (True, 4)):
            with self.subTest(anchor=anchor), self.assertRaises(RuleError):
                doc.replace(place_group_prefab(
                    doc.data, self.DST, prefab, anchor))
            self.assertEqual(doc.data, original)
            self.assertEqual(len(doc.undo_stack), history)

    def test_link_to_external_object_rejected_on_export(self):
        data = add_object(self.data, self.SRC, 'door', 'door', (5, 5))
        data = add_object(data, self.SRC, 'lever', 'switch', (6, 5),
                          link='door')
        data = create_editor_group(data, self.SRC, 'Mécanisme',
                                   cells=((6, 5),))
        with self.assertRaisesRegex(RuleError, 'linked doors'):
            capture_group_prefab(data, self.SRC,
                                 ('group_1',), 'Incomplete')

    def test_passage_destination_is_relative(self):
        data = add_object(self.data, self.SRC, 'passA', 'passage',
                          (5, 5), destination=(6, 6))
        data = create_editor_group(data, self.SRC, 'Tunnel',
                                   cells=((5, 5),))
        prefab = capture_group_prefab(data, self.SRC,
                                      ('group_1',), 'Tunnel')
        imported = place_group_prefab(data, self.DST, prefab, (11, 11))
        obj = self.mission(imported, self.DST)['objects'][0]
        self.assertEqual(tuple(obj['pos']), (11, 11))
        self.assertEqual(tuple(obj['destination']), (12, 12))

    def test_untrusted_prefab_schema_and_size_rejected(self):
        src = create_editor_group(self.data, self.SRC, 'Source',
                                  cells=((4, 4),))
        prefab = capture_group_prefab(src, self.SRC, ('group_1',), 'Source')
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'bad.json'
            broken = [
                {**prefab, 'version': 2},
                {**prefab, 'kind': 'foreign'},
                {**prefab, 'groups': prefab['groups'] * 2},
                {**prefab, 'tiles': [{**prefab['tiles'][0],
                                     'pos': [200, 200]}]},
            ]
            for bad in broken:
                path.write_text(json.dumps(bad), encoding='utf-8')
                with self.assertRaises(RuleError):
                    load_group_prefab(path)
            path.write_text('{' + ' ' * (2 * 1024 * 1024))
            with self.assertRaises(RuleError):
                load_group_prefab(path)


if __name__ == '__main__':
    unittest.main()
