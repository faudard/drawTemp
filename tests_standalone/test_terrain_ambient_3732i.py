"""3.7.32I — deterministic and gameplay-independent terrain ambience."""
from copy import deepcopy
import unittest

from sporebound.model import Board, Tile
from sporebound.terrain_ambient import (
    MAX_ANIMATED_CELLS, TICK_MS, AmbientStroke, TerrainAmbientAnimator,
    SWAY, animated_coords, phase_index, stroke_tag, strokes_for_cell,
)


class FakeCanvas:
    def __init__(self, strokes):
        self.shapes = {}
        for item, stroke in enumerate(strokes, 1):
            self.shapes[item] = [stroke.shape, stroke.coords,
                                 ('iso_ambient', stroke_tag(stroke))]

    def find_withtag(self, tag):
        return tuple(k for k, v in self.shapes.items() if tag in v[2])

    def gettags(self, item):
        return self.shapes[item][2]

    def type(self, item):
        return self.shapes[item][0]

    def coords(self, item, *coords):
        if coords:
            self.shapes[item][1] = tuple(coords)
        return self.shapes[item][1]


class AmbientTerrainTests(unittest.TestCase):
    def test_ambient_is_pure_opt_in_and_uses_existing_terrain(self):
        board = Board(16, 16)
        board.tiles[(8, 8)] = Tile(surface='grass', feature='reeds')
        copy = deepcopy(board)
        strokes = strokes_for_cell(board, (8, 8), (150, 100), 54)
        self.assertEqual(len(strokes), 3)
        self.assertEqual(strokes, strokes_for_cell(board, (8, 8), (150, 100), 54))
        self.assertEqual(strokes_for_cell(board, (8, 8), (150, 100), 54,
                                          enabled=False), ())
        self.assertEqual(board, copy)
        self.assertEqual({s.kind for s in strokes}, {'reeds'})
        self.assertTrue(all(s.coords[1] > s.coords[3] for s in strokes))

    def test_grass_ripples_and_leaves_use_only_eligible_tiles(self):
        board = Board(16, 16)
        for x in range(16):
            for y in range(16):
                board.tiles[(x, y)] = Tile(surface='water')
        puddles = [cell for cell in board.cells()
                   if strokes_for_cell(board, cell, (100, 100), 54)]
        self.assertTrue(puddles)
        self.assertTrue(all(
            all(stroke.kind == 'water' and stroke.shape == 'oval'
                for stroke in strokes_for_cell(board, cell, (100, 100), 54))
            for cell in puddles))
        # All water animations are purely visual; no new surface flags.
        self.assertEqual(board.tile(puddles[0]).surface, 'water')
        board.tiles[(8, 8)] = Tile(feature='tree', surface='grass')
        leaves = strokes_for_cell(board, (8, 8), (150, 100), 54)
        self.assertEqual(len(leaves), 2)
        self.assertTrue(all(s.kind == 'leaves' for s in leaves))
        board.tiles[(8, 8)] = Tile(surface='stone')
        self.assertEqual(strokes_for_cell(board, (8, 8), (150, 100), 54), ())

    def test_motion_is_a_pure_function_of_timestamp(self):
        board = Board(16, 16)
        board.tiles[(7, 7)] = Tile(feature='reeds')
        stroke = strokes_for_cell(board, (7, 7), (200, 160), 54)[0]
        baseline = stroke.coords
        frames = [animated_coords(stroke, step*TICK_MS) for step in range(8)]
        self.assertGreater(len(set(frames)), 2)
        self.assertTrue(all(tuple(frame[:2]) == baseline[:2]
                            for frame in frames))
        self.assertEqual(frames[0], animated_coords(stroke, 8*TICK_MS))
        self.assertEqual(phase_index(stroke, 0),
                         phase_index(stroke, 8*TICK_MS))
        with self.assertRaises(ValueError):
            phase_index(stroke, -1)

    def test_water_ripple_changes_size_without_changing_center(self):
        stroke = AmbientStroke('water', (3, 4), 0, 'oval',
                               (10, 15, 30, 25), '#b8dddd')
        frames = [animated_coords(stroke, n*TICK_MS) for n in range(8)]
        self.assertGreater(len(set(frames)), 2)
        self.assertTrue(all((p[0]+p[2], p[1]+p[3]) == (40, 40)
                            for p in frames))

    def test_item_lifecycle_rebind_restore_never_accumulates_motion(self):
        board = Board(16, 16)
        board.tiles[(8, 8)] = Tile(feature='reeds')
        original = strokes_for_cell(board, (8, 8), (150, 100), 54)
        canvas = FakeCanvas(original)
        clock = TerrainAmbientAnimator()
        self.assertEqual(clock.capture(canvas), len(original))
        self.assertTrue(clock.active)
        base = {item: canvas.coords(item) for item in canvas.find_withtag('iso_ambient')}
        snapshots = set()
        for tick in range(8):
            stamp = tick*TICK_MS
            self.assertEqual(clock.tick(canvas, stamp), len(original))
            self.assertEqual(clock.tick(canvas, stamp+1), 0)
            snapshots.add(tuple(canvas.coords(item)
                                for item in canvas.find_withtag('iso_ambient')))
        self.assertGreater(len(snapshots), 2)
        clock.restore(canvas)
        self.assertEqual(
            {item: canvas.coords(item) for item in canvas.find_withtag('iso_ambient')},
            base)
        self.assertEqual(clock.capture(canvas), len(original))
        clock.clear()
        self.assertFalse(clock.active)

    def test_large_map_density_budget(self):
        board = Board(128, 128)
        count = sum(bool(strokes_for_cell(board, c, (100, 100), 54))
                    for c in board.cells())
        # Deterministically subsample far below 16,384 redraws/tick.
        self.assertLess(count, MAX_ANIMATED_CELLS * 2)
        self.assertGreater(count, 0)


if __name__ == '__main__':
    unittest.main()
