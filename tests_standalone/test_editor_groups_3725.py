"""3.7.25 — hierarchical editor groups: persistent, atomic, Tk-independent."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_object
from sporebound.editor import Document
from sporebound.editor_architecture import EditingContext, EditorGroupMoveCommand
from sporebound.editor_groups import (
    add_selection_to_group, create_editor_group, delete_editor_group,
    descendant_groups, group_display_cells, group_selection,
    move_editor_group, rename_editor_group, reparent_editor_group)
from sporebound.iso_structures import place_structure
from sporebound.model import Content, RuleError


class EditorHierarchyTests(unittest.TestCase):
    MID = 'hierarchy'

    def setUp(self):
        self.base = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                      self.MID, 'Groupes', 24, 24)

    def groups(self, data):
        return next(m for m in data['missions'] if m['id'] == self.MID).get(
            'editor_groups', [])

    def mission(self, data):
        return next(m for m in data['missions'] if m['id'] == self.MID)

    def test_empty_group_creation_rename_and_legacy_compatibility(self):
        self.assertNotIn('editor_groups', self.mission(self.base))
        grouped = create_editor_group(self.base, self.MID, 'Décors')
        self.assertEqual(self.groups(grouped)[0]['name'], 'Décors')
        self.assertEqual(self.groups(grouped)[0]['cells'], [])
        self.assertNotIn('editor_groups', self.mission(self.base))
        renamed = rename_editor_group(grouped, self.MID, 'group_1', 'Forêt')
        self.assertEqual(self.groups(renamed)[0]['name'], 'Forêt')
        with self.assertRaises(RuleError):
            move_editor_group(renamed, self.MID, 'group_1', 1, 0)
        with TemporaryDirectory() as folder:
            doc = Document(Content.from_dict(renamed))
            path = Path(folder) / 'mission.json'
            doc.save(path)
            self.assertEqual(Content.load(path).to_dict(), renamed)
        deleted = delete_editor_group(renamed, self.MID, 'group_1')
        self.assertNotIn('editor_groups', self.mission(deleted))

    def test_tile_and_decor_move_as_a_sparse_patch_with_one_undo(self):
        doc = Document(Content.from_dict(self.base))
        doc.paint_many(self.MID, [(5, 5)], 'feature:tree')
        doc.paint_many(self.MID, [(6, 5)], 'surface:water')
        doc.replace(create_editor_group(doc.data, self.MID, 'Bosquet',
                                        cells=((5, 5), (6, 5))))
        previous = deepcopy(doc.data)
        doc.replace(move_editor_group(doc.data, self.MID, 'group_1', 2, 1))
        board = Content.from_dict(doc.data).missions[self.MID].board
        self.assertEqual(board.tile((7, 6)).feature, 'tree')
        self.assertEqual(board.tile((8, 6)).surface, 'water')
        self.assertEqual(board.tile((5, 5)).feature, '')
        self.assertEqual(board.tile((6, 5)).surface, 'grass')
        self.assertEqual(self.groups(doc.data)[0]['cells'], [[7, 6], [8, 6]])
        doc.undo()
        self.assertEqual(doc.data, previous)
        doc.redo()
        self.assertEqual(Content.from_dict(doc.data).missions[self.MID]
                         .board.tile((7, 6)).feature, 'tree')

    def test_nested_groups_move_descendants_and_preserve_member_ids(self):
        raw = add_object(self.base, self.MID, 'supply', 'chest', (8, 8))
        parent = create_editor_group(raw, self.MID, 'Campement', cells=((3, 3),))
        child = create_editor_group(parent, self.MID, 'Coffres',
                                    parent='group_1', cells=((8, 8),))
        self.assertEqual(self.groups(child)[1]['object_ids'], ['supply'])
        self.assertEqual([g['id'] for g in descendant_groups(self.mission(child),
                                                              'group_1')],
                         ['group_1', 'group_2'])
        self.assertIn((8, 8), group_display_cells(self.mission(child),
                                                  'group_1'))
        moved = move_editor_group(child, self.MID, 'group_1', 1, 0)
        self.assertEqual(self.mission(moved)['objects'][0]['pos'], [9, 8])
        self.assertEqual(self.groups(moved)[1]['parent'], 'group_1')
        self.assertEqual(self.groups(moved)[1]['cells'], [[9, 8]])
        ungrouped = delete_editor_group(moved, self.MID, 'group_1')
        self.assertEqual(self.groups(ungrouped)[0]['parent'], None)
        self.assertEqual(self.mission(ungrouped)['objects'][0]['pos'], [9, 8])

    def test_reject_cycles_duplicate_members_and_invalid_references(self):
        parent = create_editor_group(self.base, self.MID, 'Root',
                                     cells=((3, 3),))
        child = create_editor_group(parent, self.MID, 'Child',
                                    parent='group_1', cells=((5, 5),))
        with self.assertRaisesRegex(RuleError, 'Cycle'):
            reparent_editor_group(child, self.MID, 'group_1', 'group_2')
        with self.assertRaises(RuleError):
            add_selection_to_group(child, self.MID, 'group_2', ((3, 3),))
        corrupt = deepcopy(child)
        self.groups(corrupt)[1]['object_ids'] = ['missing-object']
        with self.assertRaises(RuleError):
            Content.from_dict(corrupt)
        self.assertEqual(self.groups(child)[0]['cells'], [[3, 3]])

    def test_reject_external_tile_overwrite_and_out_of_bounds_atomically(self):
        doc = Document(Content.from_dict(self.base))
        doc.paint_many(self.MID, [(4, 4)], 'feature:tree')
        doc.paint_many(self.MID, [(5, 4)], 'feature:boulder')
        doc.replace(create_editor_group(doc.data, self.MID, 'Tree',
                                        cells=((4, 4),)))
        snapshot = deepcopy(doc.data)
        history = len(doc.undo_stack)
        for dx, dy in ((1, 0), (-5, 0), (0, 50), (True, 0)):
            with self.subTest(offset=(dx, dy)), self.assertRaises(RuleError):
                doc.replace(move_editor_group(doc.data, self.MID, 'group_1',
                                              dx, dy))
            self.assertEqual(doc.data, snapshot)
            self.assertEqual(len(doc.undo_stack), history)

    def test_group_structure_and_terrain_are_distinct_members(self):
        raw = place_structure(self.base, self.MID, 'Pont', (6, 6))
        raw = create_editor_group(raw, self.MID, 'Pont + berges',
                                  cells=tuple([(x, y) for y in range(6, 8)
                                               for x in range(6, 9)] +
                                              [(5, 7)]))
        group = self.groups(raw)[0]
        self.assertEqual(len(group['structure_ids']), 1)
        self.assertEqual(group['cells'], [[5, 7]])
        sid = group['structure_ids'][0]
        # Keep the free tile clear of the translated bridge footprint.
        moved = move_editor_group(raw, self.MID, 'group_1', 0, 3)
        structure = next(s for s in self.mission(moved)['structures']
                         if s['id'] == sid)
        self.assertEqual(structure['anchor'], [6, 9])
        self.assertEqual(self.groups(moved)[0]['cells'], [[5, 10]])
        self.assertEqual(self.groups(moved)[0]['structure_ids'], [sid])

    def test_preview_is_side_effect_free_and_stale_preview_is_rejected(self):
        raw = create_editor_group(self.base, self.MID, 'Atelier',
                                  cells=((8, 8),))
        doc = Document(Content.from_dict(raw))
        ctx = EditingContext(doc, lambda: self.MID)
        before = deepcopy(doc.data)
        command = EditorGroupMoveCommand('group_1', 2, 1)
        preview = ctx.preview(command)
        self.assertEqual(doc.data, before)
        ctx.apply(preview)
        self.assertEqual(self.groups(doc.data)[0]['cells'], [[10, 9]])
        doc.undo()
        self.assertEqual(doc.data, before)
        doc.replace(create_editor_group(doc.data, self.MID, 'Autre groupe'))
        with self.assertRaises(RuleError):
            ctx.apply(preview)


if __name__ == '__main__':
    unittest.main()
