"""3.7.32A — smart Map Builder tools: deterministic cells, atomic edits, Player contract."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_connections import E, bridge_axis, shoreline_mask
from sporebound.map_builder4 import smart_brush_cells, surface_region
from sporebound.model import Content, RuleError


class MapBuilder4SmartBrushTests(unittest.TestCase):
    def setUp(self):
        original = Content.load(DEFAULT_CONTENT).to_dict()
        self.mid = 'map_builder_4a'
        self.data = add_blank_mission(original, self.mid, 'Smart brushes', 12, 12)
        self.doc = Document(Content.from_dict(self.data))

    def board(self):
        return Content.from_dict(self.doc.data).missions[self.mid].board

    def test_connected_brush_catches_pointer_jumps_without_extra_data(self):
        cells = smart_brush_cells(
            self.doc.data, self.mid, [(3, 3), (7, 3)], radius=0)
        self.assertEqual(cells, ((3, 3), (4, 3), (5, 3), (6, 3), (7, 3)))
        self.assertEqual(cells, smart_brush_cells(
            self.doc.data, self.mid, [(3, 3), (7, 3), (7, 3)], radius=0))

    def test_footprint_shapes_edge_clip_and_deterministic_order(self):
        diamond = smart_brush_cells(
            self.doc.data, self.mid, [(4, 4)], radius=1)
        self.assertEqual(diamond,
                         ((4, 3), (3, 4), (4, 4), (5, 4), (4, 5)))
        square = smart_brush_cells(
            self.doc.data, self.mid, [(4, 4)], radius=1, shape='square')
        self.assertEqual(len(square), 9)
        self.assertEqual(len(smart_brush_cells(
            self.doc.data, self.mid, [(0, 0)], radius=2)), 6)
        self.assertEqual(len(set(square)), len(square))

    def test_smart_paint_is_one_undo_and_preserves_other_tile_properties(self):
        self.doc.paint_many(self.mid, [(4, 4)], 'feature:tree')
        self.doc.paint_many(self.mid, [(4, 4)], 'height:3')
        before = deepcopy(self.doc.data)
        history = len(self.doc.undo_stack)
        count = self.doc.smart_paint(
            self.mid, [(4, 4), (6, 4)], 'surface:cobble', radius=1)
        self.assertEqual(count, 11)
        self.assertEqual(len(self.doc.undo_stack), history + 1)
        self.assertEqual(self.board().tile((4, 4)).feature, 'tree')
        self.assertEqual(self.board().tile((4, 4)).height, 3)
        self.assertEqual(self.board().tile((6, 4)).surface, 'cobble')
        self.doc.undo()
        self.assertEqual(self.doc.data, before)
        self.doc.redo()
        self.assertEqual(self.board().tile((6, 4)).surface, 'cobble')

    def test_bounded_fill_does_not_escape_selection_or_destroy_decor(self):
        self.doc.paint_many(self.mid, [(4, 4), (5, 4), (6, 4)],
                            'surface:stone')
        self.doc.paint_many(self.mid, [(4, 4)], 'feature:tree')
        self.assertEqual(surface_region(
            self.doc.data, self.mid, (4, 4),
            allowed_cells={(4, 4), (5, 4)}), ((4, 4), (5, 4)))
        before = deepcopy(self.doc.data)
        history = len(self.doc.undo_stack)
        self.assertEqual(self.doc.flood_surface(
            self.mid, (4, 4), 'dirt',
            allowed_cells={(4, 4), (5, 4)}), 2)
        self.assertEqual(len(self.doc.undo_stack), history + 1)
        self.assertEqual(self.board().tile((6, 4)).surface, 'stone')
        self.assertEqual(self.board().tile((4, 4)).feature, 'tree')
        self.doc.undo()
        self.assertEqual(self.doc.data, before)

    def test_auto_shoreline_and_bridge_geometry_reuse_existing_renderer(self):
        self.doc.paint_many(self.mid, [(4, 4)], 'surface:water')
        self.assertTrue(shoreline_mask(self.board(), (4, 4)) & E)
        self.doc.paint_many(self.mid, [(5, 4)], 'surface:bridge')
        self.assertFalse(shoreline_mask(self.board(), (4, 4)) & E)
        self.assertIn(bridge_axis(self.board(), (5, 4)), ('x', 'y'))

    def test_invalid_inputs_and_blocked_spawn_roll_back(self):
        before = deepcopy(self.doc.data)
        history = len(self.doc.undo_stack)
        examples = [
            ([(3, 3)], 4, 'diamond'),
            ([(3, 3)], True, 'diamond'),
            ([(3, 3)], 1, 'ellipse'),
            ([(12, 3)], 0, 'square'),
            ([(True, 2)], 0, 'square'),
            ([], 0, 'square'),
        ]
        for anchors, radius, shape in examples:
            with self.subTest(anchors=anchors, radius=radius, shape=shape):
                with self.assertRaises(RuleError):
                    self.doc.smart_paint(self.mid, anchors, 'surface:stone',
                                         radius=radius, shape=shape)
        with self.assertRaises(RuleError):
            self.doc.flood_surface(self.mid, (4, 4), 'dirt',
                                   allowed_cells={(5, 4)})
        with self.assertRaises(RuleError):
            self.doc.flood_surface(self.mid, (4, 4), 'dirt',
                                   allowed_cells=set())
        with self.assertRaises(RuleError):
            self.doc.smart_paint(self.mid, [(1, 10)], 'surface:water')
        with self.assertRaises(RuleError):
            self.doc.smart_paint(self.mid, [(4, 4)], 'unit')
        self.assertEqual(self.doc.data, before)
        self.assertEqual(len(self.doc.undo_stack), history)


if __name__ == '__main__':
    unittest.main()
