"""Neighbour-aware shoreline and bridge authoring contracts."""
import unittest

from sporebound.iso_connections import (N, E, S, W, shoreline_mask,
                                        waterfall_mask, bridge_axis,
                                        transition_segments, bridge_rails)
from sporebound.model import Board, Tile


class IsoConnectionsTests(unittest.TestCase):
    def setUp(self):
        self.board = Board(7, 7)

    def paint(self, cell, surface, height=0):
        self.board.tiles[cell] = Tile(surface=surface, height=height)

    def test_isolated_water_has_four_banks(self):
        self.paint((3, 3), 'water')
        self.assertEqual(shoreline_mask(self.board, (3, 3)), N | E | S | W)
        self.assertEqual(shoreline_mask(self.board, (0, 0)), 0)
        self.assertEqual(shoreline_mask(self.board, (-1, 3)), 0)

    def test_shared_water_and_bridge_edges_have_no_fake_shore(self):
        self.paint((3, 3), 'water')
        self.paint((3, 2), 'water')
        self.paint((4, 3), 'bridge')
        self.assertEqual(shoreline_mask(self.board, (3, 3)), S | W)
        self.assertEqual(shoreline_mask(self.board, (3, 2)) & S, 0)
        self.assertEqual(shoreline_mask(self.board, (4, 3)), 0)

    def test_map_edges_do_not_produce_unbounded_foam(self):
        self.paint((0, 0), 'water')
        self.assertEqual(shoreline_mask(self.board, (0, 0)), E | S)

    def test_waterfall_only_on_descending_visible_water_face(self):
        self.paint((3, 3), 'water', 3)
        self.paint((4, 3), 'water', 1)
        self.paint((3, 4), 'water', 2)
        self.paint((2, 3), 'water', 0)
        self.paint((3, 2), 'water', 0)
        self.assertEqual(waterfall_mask(self.board, (3, 3)), E | S)
        self.paint((4, 3), 'water', 3)
        self.paint((3, 4), 'bridge', 0)
        self.assertEqual(waterfall_mask(self.board, (3, 3)), 0)

    def test_river_flow_auto_selects_crossing_axis(self):
        self.paint((3, 3), 'bridge')
        self.paint((3, 2), 'water')
        self.paint((3, 4), 'water')
        self.assertEqual(bridge_axis(self.board, (3, 3)), 'x')
        self.paint((3, 2), 'grass')
        self.paint((3, 4), 'grass')
        self.paint((2, 3), 'water')
        self.paint((4, 3), 'water')
        self.assertEqual(bridge_axis(self.board, (3, 3)), 'y')
        self.assertIsNone(bridge_axis(self.board, (3, 4)))

    def test_geometry_segments_match_mask(self):
        north, east, south, west = ((0, -1), (1, 0), (0, 1), (-1, 0))
        corners = (north, east, south, west)
        self.assertEqual(transition_segments(corners, E | W),
                         ((east, south), (north, east)))
        self.assertEqual(bridge_rails(corners, 'x'),
                         ((west, north), (south, east)))
        self.assertEqual(bridge_rails(corners, 'y'),
                         ((north, east), (west, south)))


if __name__ == '__main__':
    unittest.main()
