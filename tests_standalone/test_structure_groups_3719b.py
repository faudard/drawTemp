"""3.7.19B — transaction tests for complete multi-structure editing."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_structures import (place_structure, structure_at,
                                       structure_template)
from sporebound.map_authoring import paste_terrain
from sporebound.model import Content, RuleError
from sporebound.structure_groups import selected_structures, transform_structure_group


class StructureGroupEditingTests(unittest.TestCase):
    MID = "structure_groups"

    def setUp(self):
        base = Content.load(DEFAULT_CONTENT)
        data = add_blank_mission(base.to_dict(), self.MID, "Groupes", 24, 20)
        self.doc = Document(Content.from_dict(data))
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         "Maison", (3, 4)))
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         "Tour", (7, 4)))

    def region(self):
        # Explicit union of the *full* footprints; not just clicked anchors.
        scene = Content.from_dict(self.doc.data).missions[self.MID]
        from sporebound.iso_architecture import architecture_instances
        instances = architecture_instances(scene.board, scene.structures)
        return tuple(sorted(set().union(*(i.cells for i in instances))))

    def records(self):
        return Content.from_dict(self.doc.data).missions[self.MID].structures

    def test_adjacent_group_move_one_tile_keeps_identity_and_undo(self):
        original = deepcopy(self.doc.data)
        ids = {row['id']: tuple(row['anchor']) for row in self.records()}
        result = transform_structure_group(self.doc.data, self.MID,
                                           self.region(), 1, 0)
        self.assertEqual(self.doc.data, original)
        self.doc.replace(result)
        new = {row['id']: tuple(row['anchor']) for row in self.records()}
        self.assertEqual(new, {key: (pos[0] + 1, pos[1])
                               for key, pos in ids.items()})
        self.doc.undo()
        self.assertEqual(self.doc.data, original)
        self.doc.redo()
        self.assertEqual({row['id']: tuple(row['anchor'])
                          for row in self.records()}, new)

    def test_group_duplicate_creates_unique_id_and_save_reopen(self):
        selection = self.region()
        self.doc.replace(transform_structure_group(self.doc.data, self.MID,
                                                     selection, 0, 7,
                                                     duplicate=True))
        self.assertEqual(len(self.records()), 4)
        self.assertEqual(len({r['id'] for r in self.records()}), 4)
        with TemporaryDirectory() as directory:
            target = Path(directory) / 'content.json'
            self.doc.save(target)
            reopened = Content.load(target).missions[self.MID]
            self.assertEqual(reopened.structures, self.records())
        self.doc.undo()
        self.assertEqual(len(self.records()), 2)

    def test_partial_selection_does_not_select_building(self):
        selected = ((3, 4), (4, 4))
        self.assertEqual(selected_structures(self.doc.data, self.MID,
                                             selected), ())
        before = deepcopy(self.doc.data)
        with self.assertRaisesRegex(RuleError, 'complete footprint'):
            transform_structure_group(self.doc.data, self.MID, selected, 1, 0)
        self.assertEqual(self.doc.data, before)

    def test_invalid_group_is_atomic(self):
        selection = self.region()
        before = deepcopy(self.doc.data)
        undo_count = len(self.doc.undo_stack)
        actions = (
            lambda: transform_structure_group(self.doc.data, self.MID,
                                              selection, 30, 0),
            lambda: transform_structure_group(self.doc.data, self.MID,
                                              selection, 0, 0, duplicate=True),
            lambda: transform_structure_group(self.doc.data, self.MID,
                                              selection, True, 0),
            lambda: transform_structure_group(self.doc.data, self.MID,
                                              selection, 1, 0, duplicate=True),
        )
        for act in actions:
            with self.subTest(action=act), self.assertRaises(RuleError):
                self.doc.replace(act())
            self.assertEqual(self.doc.data, before)
            self.assertEqual(len(self.doc.undo_stack), undo_count)

    def test_legacy_and_persistent_group_move_and_id_promotion(self):
        # Add one intact legacy stamp which has no stored structure record.
        old = paste_terrain(self.doc.data, self.MID,
                            structure_template('Pont'), (14, 8))
        self.doc.replace(old)
        whole_selection = self.region()
        found = selected_structures(self.doc.data, self.MID, whole_selection)
        self.assertEqual(len(found), 3)
        self.assertEqual(len([item for item in found if not item.id]), 1)
        moved = transform_structure_group(self.doc.data, self.MID,
                                           whole_selection, 1, 0)
        self.doc.replace(moved)
        self.assertEqual(len(self.records()), 3)
        self.assertEqual(len({r['id'] for r in self.records()}), 3)
        self.assertEqual(structure_at(self.doc.data, self.MID, (15, 8)).name,
                         'Pont')

    def test_zero_move_is_noop(self):
        original = deepcopy(self.doc.data)
        result = transform_structure_group(self.doc.data, self.MID,
                                           self.region(), 0, 0)
        self.assertEqual(result, original)


if __name__ == '__main__':
    unittest.main()
