"""3.7.11 map authoring: bounded, validated, atomic four-connected surface fill."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.model import Content, RuleError


class SurfaceFillTests(unittest.TestCase):
    def setUp(self):
        payload = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                    'fill_sandbox', 'Fill sandbox', 12, 12)
        self.doc = Document(Content.from_dict(payload))
        self.mid = 'fill_sandbox'

    def tile(self, cell):
        return Content.from_dict(self.doc.data).missions[self.mid].board.tile(cell)

    def test_four_connected_fill_preserves_existing_layers_and_undo(self):
        self.doc.paint_many(self.mid, [(4, 4), (4, 5), (8, 8)],
                            'surface:stone')
        self.doc.paint_many(self.mid, [(4, 4)], 'feature:tree')
        self.doc.paint_many(self.mid, [(4, 4)], 'height:3')
        before = deepcopy(self.doc.data)
        history = len(self.doc.undo_stack)

        self.assertEqual(self.doc.flood_surface(self.mid, (4, 4), 'cobble'), 2)
        self.assertEqual(len(self.doc.undo_stack), history + 1)
        self.assertEqual(self.tile((4, 4)).surface, 'cobble')
        self.assertEqual(self.tile((4, 5)).surface, 'cobble')
        self.assertEqual(self.tile((8, 8)).surface, 'stone')
        self.assertEqual(self.tile((5, 4)).surface, 'grass')
        self.assertEqual(self.tile((4, 4)).height, 3)
        self.assertEqual(self.tile((4, 4)).feature, 'tree')
        self.doc.undo()
        self.assertEqual(self.doc.data, before)
        self.doc.redo()
        self.assertEqual(self.tile((4, 4)).surface, 'cobble')

    def test_diagonal_cells_are_not_connected(self):
        self.doc.paint_many(self.mid, [(4, 4), (5, 5)], 'surface:stone')
        self.assertEqual(self.doc.flood_surface(self.mid, (4, 4), 'sand'), 1)
        self.assertEqual(self.tile((5, 5)).surface, 'stone')

    def test_sparse_default_grass_noop_and_invalid_inputs(self):
        history = len(self.doc.undo_stack)
        self.assertEqual(self.doc.flood_surface(self.mid, (3, 3), 'grass'), 0)
        self.assertEqual(len(self.doc.undo_stack), history)
        before = deepcopy(self.doc.data)
        for cell, surface in [((12, 3), 'sand'), ((-1, 2), 'grass'),
                              ((True, 2), 'sand'), ((2, 2), 'lava'),
                              ((2,), 'stone')]:
            with self.subTest(cell=cell, surface=surface), self.assertRaises(RuleError):
                self.doc.flood_surface(self.mid, cell, surface)
            self.assertEqual(self.doc.data, before)
            self.assertEqual(len(self.doc.undo_stack), history)

    def test_illegal_flood_rolls_back_all_cells_and_history(self):
        before = deepcopy(self.doc.data)
        undo = list(self.doc.undo_stack)
        redo = list(self.doc.redo_stack)
        # A broad water fill includes the mandatory player deployment/spawn.
        with self.assertRaises(RuleError):
            self.doc.flood_surface(self.mid, (3, 3), 'water')
        self.assertEqual(self.doc.data, before)
        self.assertEqual(self.doc.undo_stack, undo)
        self.assertEqual(self.doc.redo_stack, redo)


if __name__ == '__main__':
    unittest.main()
