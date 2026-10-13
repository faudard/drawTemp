"""3.7.25 — hierarchical editor groups: persistent, atomic, Tk-independent."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_object
from sporebound.editor import Document
from sporebound.editor_architecture import (EditingContext, EditorGroupMoveCommand,
                                           EditorGroupTreeDropCommand)
from sporebound.editor_groups import (
    add_selection_to_group, create_editor_group, delete_editor_group,
    descendant_groups, group_display_cells, group_selection,
    move_editor_group, rename_editor_group, reparent_editor_group,
    remove_selection_from_group, transfer_selection_to_group,
    check_tree_drop, drop_group_tree_item)
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

    def test_transfer_unlink_and_change_parent(self):
        first = create_editor_group(self.base, self.MID, 'A',
                                    cells=((3, 3),))
        second = create_editor_group(first, self.MID, 'B',
                                     cells=((5, 5),))
        reassigned = transfer_selection_to_group(
            second, self.MID, 'group_2', ((3, 3),))
        self.assertEqual(self.groups(reassigned)[0]['cells'], [])
        self.assertEqual(self.groups(reassigned)[1]['cells'],
                         [[5, 5], [3, 3]])
        after_unlink = remove_selection_from_group(
            reassigned, self.MID, 'group_2', ((3, 3),))
        self.assertEqual(self.groups(after_unlink)[1]['cells'], [[5, 5]])
        reparented = reparent_editor_group(after_unlink, self.MID,
                                           'group_2', 'group_1')
        self.assertEqual(self.groups(reparented)[1]['parent'], 'group_1')
        root_again = reparent_editor_group(reparented, self.MID,
                                            'group_2', None)
        self.assertIsNone(self.groups(root_again)[1]['parent'])

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

    def test_existing_structure_edit_and_delete_keep_group_valid(self):
        from sporebound.iso_structures import edit_structure, remove_structure
        raw = place_structure(self.base, self.MID, 'Pont', (6, 6))
        region = [(x, y) for y in range(6, 8) for x in range(6, 9)]
        grouped = create_editor_group(raw, self.MID, 'Passerelle',
                                      cells=region)
        sid = self.groups(grouped)[0]['structure_ids'][0]
        moved = edit_structure(grouped, self.MID, (6, 6), anchor=(11, 11))
        self.assertEqual(self.groups(moved)[0]['structure_ids'], [sid])
        self.assertEqual(next(s for s in self.mission(moved)['structures']
                              if s['id'] == sid)['anchor'], [11, 11])
        removed = remove_structure(moved, self.MID, (11, 11))
        self.assertEqual(self.groups(removed)[0]['structure_ids'], [])
        self.assertEqual(len(self.mission(removed)['structures']), 0)

    def test_entity_delete_dissociates_reference_but_preserves_terrain(self):
        from sporebound.entity_editing import remove_entity
        raw = add_object(self.base, self.MID, 'supply', 'chest', (8, 8))
        grouped = create_editor_group(raw, self.MID, 'Matériel',
                                      cells=((8, 8),))
        self.assertIn('supply', self.groups(grouped)[0]['object_ids'])
        result = remove_entity(grouped, self.MID, 'object', 'supply')
        self.assertEqual(self.groups(result)[0]['object_ids'], [])
        self.assertEqual(self.groups(result)[0]['cells'], [[8, 8]])

    def test_tree_drop_reparents_subtrees_and_rejects_cycles(self):
        first = create_editor_group(self.base, self.MID, 'Cour',
                                    cells=((3, 3),))
        second = create_editor_group(first, self.MID, 'Maison',
                                     parent='group_1', cells=((5, 5),))
        third = create_editor_group(second, self.MID, 'Quartier')
        doc = Document(Content.from_dict(third))
        original = deepcopy(doc.data)
        with self.assertRaisesRegex(RuleError, 'descendants'):
            drop_group_tree_item(doc.data, self.MID, 'group_1', 'group',
                                 target_group_id='group_2')
        with self.assertRaisesRegex(RuleError, 'already'):
            drop_group_tree_item(doc.data, self.MID, 'group_2', 'group',
                                 target_group_id='group_1')
        doc.replace(drop_group_tree_item(doc.data, self.MID,
                                         'group_3', 'group',
                                         target_group_id='group_2'))
        self.assertEqual(self.groups(doc.data)[2]['parent'], 'group_2')
        doc.replace(drop_group_tree_item(doc.data, self.MID,
                                         'group_2', 'group',
                                         target_group_id=None))
        self.assertIsNone(self.groups(doc.data)[1]['parent'])
        self.assertEqual(self.groups(doc.data)[2]['parent'], 'group_2')
        doc.undo()
        self.assertEqual(self.groups(doc.data)[1]['parent'], 'group_1')
        doc.redo()
        self.assertIsNone(self.groups(doc.data)[1]['parent'])
        self.assertEqual(self.groups(original)[0]['parent'], None)

    def test_tree_drag_cells_individually_and_as_bundle(self):
        first = create_editor_group(self.base, self.MID, 'Forêt',
                                    cells=((3, 3), (4, 3), (5, 3)))
        second = create_editor_group(first, self.MID, 'Bosquet')
        before = deepcopy(second)
        self.assertTrue(check_tree_drop(self.mission(second), 'group_1',
                                        'cell', member=(4, 3),
                                        target_group_id='group_2'))
        moved = drop_group_tree_item(second, self.MID, 'group_1', 'cell',
                                     member=(4, 3), target_group_id='group_2')
        self.assertEqual(self.groups(moved)[0]['cells'], [[3, 3], [5, 3]])
        self.assertEqual(self.groups(moved)[1]['cells'], [[4, 3]])
        all_moved = drop_group_tree_item(moved, self.MID, 'group_1',
                                         'cells', target_group_id='group_2')
        self.assertEqual(self.groups(all_moved)[0]['cells'], [])
        self.assertEqual(self.groups(all_moved)[1]['cells'],
                         [[4, 3], [3, 3], [5, 3]])
        unlinked = drop_group_tree_item(all_moved, self.MID, 'group_2',
                                        'cell', member=(4, 3),
                                        target_group_id=None)
        self.assertEqual(self.groups(unlinked)[1]['cells'], [[3, 3], [5, 3]])
        self.assertEqual(self.groups(before)[0]['cells'],
                         [[3, 3], [4, 3], [5, 3]])
        with self.assertRaises(RuleError):
            drop_group_tree_item(unlinked, self.MID, 'group_1', 'cell',
                                 member=(4, 3), target_group_id='group_2')

    def test_tree_drag_objects_and_structures_does_not_change_positions(self):
        data = add_object(self.base, self.MID, 'supply', 'chest', (8, 8))
        data = place_structure(data, self.MID, 'Pont', (12, 12))
        selected = [(8, 8)] + [(x, y) for y in range(12, 14)
                                for x in range(12, 15)]
        first = create_editor_group(data, self.MID, 'Éléments',
                                    cells=selected)
        second = create_editor_group(first, self.MID, 'Décorations')
        sid = self.groups(second)[0]['structure_ids'][0]
        doc = Document(Content.from_dict(second))
        baseline = deepcopy(doc.data)
        for field, item in (('object_ids', 'supply'),
                            ('structure_ids', sid)):
            cmd = EditorGroupTreeDropCommand('group_1', field,
                                             item, 'group_2')
            preview = EditingContext(doc, lambda: self.MID).preview(cmd)
            self.assertEqual(preview.mission_id, self.MID)
            doc.replace(preview.candidate)
        self.assertEqual(self.groups(doc.data)[0]['object_ids'], [])
        self.assertEqual(self.groups(doc.data)[1]['object_ids'], ['supply'])
        self.assertEqual(self.groups(doc.data)[1]['structure_ids'], [sid])
        self.assertEqual(self.mission(doc.data)['objects'][0]['pos'], [8, 8])
        self.assertEqual(self.mission(doc.data)['structures'][0]['anchor'], [12, 12])
        unlinked = drop_group_tree_item(doc.data, self.MID, 'group_2',
                                        'object_ids', member='supply')
        self.assertEqual(self.groups(unlinked)[1]['object_ids'], [])
        self.assertEqual(self.mission(unlinked)['objects'][0]['pos'], [8, 8])
        doc.undo()
        self.assertEqual(self.groups(doc.data)[0]['structure_ids'], [sid])
        doc.undo()
        self.assertEqual(doc.data, baseline)

    def test_tree_drop_invalid_is_atomic_and_does_not_write_history(self):
        doc = Document(Content.from_dict(
            create_editor_group(self.base, self.MID, 'Vide')))
        original = deepcopy(doc.data)
        count = len(doc.undo_stack)
        for args in (
            ('group_1', 'group', None, 'group_1'),
            ('group_1', 'cells', None, None),
            ('group_1', 'object_ids', 'unknown', None),
            ('group_1', 'cell', (200, 2), None),
            ('missing', 'group', None, None),
            ('group_1', 'group', None, 'missing'),
        ):
            with self.subTest(args=args), self.assertRaises(RuleError):
                doc.replace(drop_group_tree_item(
                    doc.data, self.MID, args[0], args[1], member=args[2],
                    target_group_id=args[3]))
            self.assertEqual(doc.data, original)
            self.assertEqual(len(doc.undo_stack), count)

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
