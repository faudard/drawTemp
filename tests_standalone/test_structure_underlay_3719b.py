"""3.7.19B: reversible terrain under authored structures, single and group edits."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_structures import (
    place_structure, remove_structure, move_structure, duplicate_structure,
    edit_structure, structure_template,
)
from sporebound.map_authoring import paste_terrain
from sporebound.model import Content, RuleError
from sporebound.structure_groups import (
    selected_structures, transform_structure_group,
)


def board_tiles(data, mid):
    return {
        tuple(entry['pos']): {k: v for k, v in entry.items() if k != 'pos'}
        for entry in next(m for m in data['missions'] if m['id'] == mid)['board']['tiles']
    }


class StructureUnderlayTests(unittest.TestCase):
    MID = 'reversible_buildings'

    def setUp(self):
        base = Content.load(DEFAULT_CONTENT).to_dict()
        data = add_blank_mission(base, self.MID, 'Atelier', 24, 20)
        mission = next(m for m in data['missions'] if m['id'] == self.MID)
        # Only two explicit cells in an otherwise sparse board. Both would
        # previously have been destroyed by placing and moving a house.
        mission['board']['tiles'] = [
            {'pos': [3, 3], 'surface': 'water', 'blocked': True,
             'height': 1},
            {'pos': [4, 4], 'surface': 'cobble', 'feature': 'tree',
             'height': 3, 'cost': 2, 'cover': 10},
        ]
        self.doc = Document(Content.from_dict(data))
        self.ground = board_tiles(self.doc.data, self.MID)

    def structures(self):
        return next(m for m in self.doc.data['missions']
                    if m['id'] == self.MID)['structures']

    def test_remove_restores_exact_sparse_background(self):
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         'Maison', (3, 3)))
        row = self.structures()[0]
        self.assertEqual(len(row['underlay']), 12)
        self.assertEqual(sum(e['tile'] is None for e in row['underlay']), 10)
        self.doc.paint_many(self.MID, [(4, 4)], 'feature-erase')
        self.doc.replace(remove_structure(self.doc.data, self.MID, (4, 4)))
        self.assertEqual(board_tiles(self.doc.data, self.MID), self.ground)
        self.assertFalse(self.structures())

    def test_overlapping_move_then_remove_restores_original_ground(self):
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         'Maison', (3, 3)))
        sid = self.structures()[0]['id']
        original = deepcopy(self.doc.data)
        self.doc.replace(move_structure(self.doc.data, self.MID,
                                        (4, 4), (4, 3)))
        self.assertEqual(self.structures()[0]['id'], sid)
        self.assertEqual(board_tiles(self.doc.data, self.MID)[(3, 3)],
                         self.ground[(3, 3)])
        self.assertTrue(any(tuple(row['pos']) == (4, 4) and
                            row['tile'] == self.ground[(4, 4)]
                            for row in self.structures()[0]['underlay']))
        self.doc.replace(remove_structure(self.doc.data, self.MID, (5, 4)))
        self.assertEqual(board_tiles(self.doc.data, self.MID), self.ground)
        self.doc.undo()
        self.doc.undo()
        self.assertEqual(self.doc.data, original)
        self.doc.redo()
        self.doc.redo()
        self.assertEqual(board_tiles(self.doc.data, self.MID), self.ground)

    def test_duplicate_preserves_each_independent_background(self):
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         'Maison', (3, 3)))
        self.doc.replace(duplicate_structure(self.doc.data, self.MID,
                                             (4, 4), (12, 7)))
        self.assertEqual(len(self.structures()), 2)
        self.assertEqual(len({r['id'] for r in self.structures()}), 2)
        self.doc.replace(remove_structure(self.doc.data, self.MID, (13, 8)))
        self.doc.replace(remove_structure(self.doc.data, self.MID, (4, 4)))
        self.assertEqual(board_tiles(self.doc.data, self.MID), self.ground)

    def test_rotation_and_type_change_restore_original_ground(self):
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         'Maison', (3, 3)))
        self.doc.replace(edit_structure(
            self.doc.data, self.MID, (4, 4),
            name='Tour', anchor=(7, 5), quarter_turns=1))
        self.doc.replace(remove_structure(self.doc.data, self.MID, (8, 6)))
        self.assertEqual(board_tiles(self.doc.data, self.MID), self.ground)

    def test_group_move_restores_all_sources_before_destination_capture(self):
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         'Maison', (3, 3)))
        # Buildings touch along x=7, so translating right by one makes
        # the first building occupy a former cell of the second.
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         'Maison', (7, 3)))
        before = deepcopy(self.doc.data)
        scene = Content.from_dict(self.doc.data).missions[self.MID]
        from sporebound.iso_architecture import architecture_instances
        instances = architecture_instances(scene.board, scene.structures)
        cells = set().union(*(item.cells for item in instances))
        self.doc.replace(transform_structure_group(self.doc.data, self.MID,
                                                     cells, 1, 0))
        self.assertEqual({tuple(r['anchor']) for r in self.structures()},
                         {(4, 3), (8, 3)})
        for cell in ((5, 4), (9, 4)):
            self.doc.replace(remove_structure(self.doc.data, self.MID, cell))
        self.assertEqual(board_tiles(self.doc.data, self.MID), self.ground)
        for _ in range(3):
            self.doc.undo()
        self.assertEqual(self.doc.data, before)

    def test_new_snapshot_survives_save_and_reopen(self):
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         'Maison', (3, 3)))
        with TemporaryDirectory() as directory:
            target = Path(directory) / 'content.json'
            self.doc.save(target)
            reopened = Content.load(target)
            self.assertEqual(reopened.missions[self.MID].structures,
                             self.structures())
            clean = remove_structure(reopened.to_dict(), self.MID, (4, 4))
            self.assertEqual(board_tiles(clean, self.MID), self.ground)

    def test_legacy_record_without_snapshot_retains_old_semantics(self):
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         'Maison', (3, 3)))
        without = deepcopy(self.doc.data)
        old_record = next(m for m in without['missions']
                          if m['id'] == self.MID)['structures'][0]
        del old_record['underlay']
        self.assertNotIn('underlay', Content.from_dict(
            without).missions[self.MID].structures[0])
        removed = remove_structure(without, self.MID, (4, 4))
        self.assertNotIn((3, 3), board_tiles(removed, self.MID))
        # Truly old stamp-only documents also retain their behavior.
        plain = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                  'stamp_only', 'Legacy', 20, 20)
        stamped = paste_terrain(plain, 'stamp_only',
                                structure_template('Maison'), (3, 3))
        self.assertNotIn('structures', next(m for m in stamped['missions']
                                           if m['id'] == 'stamp_only'))
        cleaned = remove_structure(stamped, 'stamp_only', (4, 4))
        self.assertFalse(board_tiles(cleaned, 'stamp_only'))

    def test_malformed_snapshots_rejected_and_doc_untouched(self):
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         'Maison', (3, 3)))
        clean = deepcopy(self.doc.data)
        original = self.structures()[0]['underlay']
        variants = [
            original[:-1],
            [original[0]] + original[:-1],
            [{**original[0], 'pos': [20, 19]}] + original[1:],
            [{**original[0], 'tile': {'surface': 'water'}}] + original[1:],
            [{**original[0], 'tile': {**self.ground[(3, 3)],
                                     'blocked': 'yes'}}] + original[1:],
        ]
        for broken_snapshot in variants:
            invalid = deepcopy(clean)
            record = next(m for m in invalid['missions']
                          if m['id'] == self.MID)['structures'][0]
            record['underlay'] = broken_snapshot
            with self.subTest(snapshot=broken_snapshot[:1]):
                with self.assertRaises(RuleError):
                    Content.from_dict(invalid)
                self.assertEqual(self.doc.data, clean)


if __name__ == '__main__':
    unittest.main()
