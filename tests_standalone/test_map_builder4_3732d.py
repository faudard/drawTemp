"""Map Builder 4.0D — rotation and live-stamping reuse the 3.7.25D prefab format."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_object
from sporebound.editor import Document
from sporebound.editor_architecture import EditingContext, GroupPrefabPlaceCommand
from sporebound.editor_groups import create_editor_group
from sporebound.group_prefabs import capture_group_prefab, place_group_prefab, prefab_display_cells
from sporebound.group_prefab_transform import rotate_group_prefab
from sporebound.interior_levels import add_interior_floor
from sporebound.iso_structures import place_structure
from sporebound.level_navigation import add_level_link, place_unit_on_level
from sporebound.model import Content, RuleError


class ReusablePrefab4Tests(unittest.TestCase):
    SRC = 'prefab_rot_src'
    DST = 'prefab_rot_dst'

    def setUp(self):
        raw = Content.load(DEFAULT_CONTENT).to_dict()
        raw = add_blank_mission(raw, self.SRC, 'Source', 30, 30)
        self.raw = add_blank_mission(raw, self.DST, 'Destination', 30, 30)

    def mission(self, raw, mid):
        return next(m for m in raw['missions'] if m['id'] == mid)

    def test_road_and_decor_rotation_roundtrip_and_single_undo(self):
        doc = Document(Content.from_dict(self.raw))
        doc.paint_many(self.SRC, [(5, 4)], 'surface:cobble')
        doc.paint_many(self.SRC, [(6, 4)], 'feature:tree')
        source = create_editor_group(doc.data, self.SRC, 'Rue & jardin',
                                     cells=[(5, 4), (6, 4)])
        stamp = capture_group_prefab(source, self.SRC, ('group_1',), 'Rue')
        self.assertEqual(stamp['size'], [2, 1])
        original = deepcopy(stamp)
        rotated = rotate_group_prefab(stamp, 1)
        self.assertEqual(rotated['size'], [1, 2])
        self.assertEqual({tuple(t['pos']) for t in rotated['tiles']},
                         {(0, 0), (0, 1)})
        self.assertEqual(rotate_group_prefab(rotated, 3), stamp)
        self.assertEqual(stamp, original)
        canvas_cells = prefab_display_cells(rotated, (12, 12))
        self.assertEqual(canvas_cells, {(12, 12), (12, 13)})
        document = Document(Content.from_dict(source))
        context = EditingContext(document, lambda: self.DST)
        baseline = deepcopy(document.data)
        command = GroupPrefabPlaceCommand(rotated, (12, 12))
        prepared = context.preview(command)
        self.assertEqual(document.data, baseline)
        context.apply(prepared)
        board = Content.from_dict(document.data).missions[self.DST].board
        self.assertEqual(board.tile((12, 12)).surface, 'cobble')
        self.assertEqual(board.tile((12, 13)).feature, 'tree')
        document.undo()
        self.assertEqual(document.data, baseline)
        document.redo()
        self.assertEqual(Content.from_dict(document.data).missions[self.DST]
                         .board.tile((12, 13)).feature, 'tree')

    def test_nested_groups_linked_door_and_switch_rotate_together(self):
        data = add_object(self.raw, self.SRC, 'door_rot', 'door', (7, 6))
        data = add_object(data, self.SRC, 'switch_rot', 'switch', (9, 6),
                          link='door_rot')
        data = create_editor_group(data, self.SRC, 'Enceinte', cells=[(7, 6)])
        data = create_editor_group(data, self.SRC, 'Mécanisme', parent='group_1',
                                   cells=[(9, 6)])
        original = capture_group_prefab(data, self.SRC, ('group_1',), 'Porte et levier')
        rotated = rotate_group_prefab(original, 1)
        self.assertEqual(rotated['size'], [1, 3])
        imported = place_group_prefab(data, self.DST, rotated, (18, 10))
        objs = self.mission(imported, self.DST)['objects']
        door = next(o for o in objs if o['kind'] == 'door')
        lever = next(o for o in objs if o['kind'] == 'switch')
        self.assertEqual(tuple(door['pos']), (18, 10))
        self.assertEqual(tuple(lever['pos']), (18, 12))
        self.assertEqual(lever['link'], door['id'])
        groups = self.mission(imported, self.DST)['editor_groups']
        self.assertEqual(groups[1]['parent'], groups[0]['id'])
        Content.from_dict(imported)

    def test_upper_decks_stairs_and_actor_survive_rotation(self):
        data = place_structure(self.raw, self.SRC, 'Tour', (7, 7))
        sid = self.mission(data, self.SRC)['structures'][0]['id']
        data = add_interior_floor(data, self.SRC, sid, 1)
        data = add_level_link(data, self.SRC, (0, 8, 9), (1, 8, 8))
        uid = self.mission(data, self.SRC)['units'][0]['id']
        data = place_unit_on_level(data, self.SRC, uid, 1, (8, 8))
        data = create_editor_group(data, self.SRC, 'Tour avec escalier',
                                   cells=[(x, y) for y in range(7, 10)
                                          for x in range(7, 10)])
        prefab = capture_group_prefab(data, self.SRC, ('group_1',), 'Tour + escalier')
        rotated = rotate_group_prefab(prefab, 1)
        self.assertEqual(rotated['structures'][0]['turns'], 1)
        self.assertEqual(rotated['level_links'][0]['from'], [0, 0, 1])
        self.assertEqual(rotated['level_links'][0]['to'], [1, 1, 1])
        pasted = place_group_prefab(data, self.DST, rotated, (14, 14))
        mission = Content.from_dict(pasted).missions[self.DST]
        self.assertEqual(mission.structures[0]['turns'], 1)
        self.assertEqual(len(mission.interior_floors), 1)
        self.assertEqual(mission.level_links[0]['from'], [0, 14, 15])
        self.assertEqual(mission.level_links[0]['to'], [1, 15, 15])
        self.assertEqual(mission.unit_levels[self.mission(pasted, self.DST)
                                             ['editor_groups'][0]['unit_ids'][0]], 1)
        self.assertEqual(rotate_group_prefab(rotated, 3), prefab)

    def test_blocked_rotated_prefab_has_no_effect(self):
        raw = create_editor_group(self.raw, self.SRC, 'Herbe',
                                  cells=[(4, 4), (5, 4)])
        prefab = rotate_group_prefab(capture_group_prefab(
            raw, self.SRC, ('group_1',), 'Terrain'), 1)
        doc = Document(Content.from_dict(raw))
        doc.paint_many(self.DST, [(13, 13)], 'feature:tree')
        before = deepcopy(doc.data)
        before_history = len(doc.undo_stack)
        for anchor in ((13, 13), (29, 29), (-1, 0)):
            with self.subTest(anchor=anchor), self.assertRaises(RuleError):
                doc.replace(place_group_prefab(doc.data, self.DST, prefab, anchor))
            self.assertEqual(doc.data, before)
            self.assertEqual(len(doc.undo_stack), before_history)

    def test_invalid_quarter_turns_rejected(self):
        raw = create_editor_group(self.raw, self.SRC, 'Sol', cells=[(4, 4)])
        prefab = capture_group_prefab(raw, self.SRC, ('group_1',), 'Sol')
        for turns in (-1, 4, True, '90', 0.5):
            with self.subTest(turns=turns), self.assertRaises(RuleError):
                rotate_group_prefab(prefab, turns)


if __name__ == '__main__':
    unittest.main()
