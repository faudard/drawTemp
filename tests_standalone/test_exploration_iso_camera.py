"""Regression tests for the narrative Player's map-only camera controls."""
import unittest

from sporebound.exploration_iso_view import (
    IsoExplorationCanvas, anchored_exploration_zoom,
    exploration_iso_pick, exploration_iso_shift, exploration_visual_board)
from sporebound.iso_map import IsoGeometry


STAGE = {
    "width": 9, "height": 6, "theme": "fields",
    "blocked": [[4, 2], [6, 3]],
}


class RecordingCanvas:
    def __init__(self):
        self.moves = []

    def move(self, tag, dx, dy):
        self.moves.append((tag, dx, dy))


class ExplorationCameraTests(unittest.TestCase):
    def setUp(self):
        self.board = exploration_visual_board(STAGE)
        self.viewport = (900, 620)
        self.pan = (27, -13)

    def screen_center(self, cell, size, pan):
        geometry = IsoGeometry(self.board, size)
        shift = exploration_iso_shift(geometry, self.viewport)
        center = geometry.center(cell)
        return (center[0] + shift[0] + pan[0],
                center[1] + shift[1] + pan[1])

    def test_zoom_keeps_pointer_tile_and_center_stable(self):
        cell = (3, 2)
        original = self.screen_center(cell, 48, self.pan)
        new_pan = anchored_exploration_zoom(
            self.board, 48, 72, self.viewport, self.pan, original)
        moved = self.screen_center(cell, 72, new_pan)
        self.assertAlmostEqual(moved[0], original[0])
        self.assertAlmostEqual(moved[1], original[1])
        geometry = IsoGeometry(self.board, 72)
        shift = exploration_iso_shift(geometry, self.viewport)
        shift = (shift[0] + new_pan[0], shift[1] + new_pan[1])
        self.assertEqual(exploration_iso_pick(geometry, shift, *original), cell)

    def test_zoom_out_round_trip_preserves_camera_and_game_board(self):
        position = (2, 4)
        original = self.screen_center(position, 48, self.pan)
        board_before = self.board.to_dict() if hasattr(self.board, "to_dict") else dict(self.board.tiles)
        enlarged = anchored_exploration_zoom(
            self.board, 48, 64, self.viewport, self.pan, original)
        restored = anchored_exploration_zoom(
            self.board, 64, 48, self.viewport, enlarged, original)
        self.assertAlmostEqual(restored[0], self.pan[0])
        self.assertAlmostEqual(restored[1], self.pan[1])
        board_after = self.board.to_dict() if hasattr(self.board, "to_dict") else dict(self.board.tiles)
        self.assertEqual(board_after, board_before)

    def test_zoom_outside_map_does_not_jump(self):
        self.assertEqual(
            anchored_exploration_zoom(self.board, 48, 56, self.viewport,
                                      self.pan, (-5000, -5000)), self.pan)

    def test_pan_updates_picking_without_touching_grid(self):
        canvas = RecordingCanvas()
        adapter = IsoExplorationCanvas.__new__(IsoExplorationCanvas)
        adapter.canvas = canvas
        adapter.pan = self.pan
        adapter.geometry = IsoGeometry(self.board, 48)
        center = exploration_iso_shift(adapter.geometry, self.viewport)
        adapter.shift = (center[0] + self.pan[0], center[1] + self.pan[1])
        cell = (5, 1)
        x, y = self.screen_center(cell, 48, self.pan)
        adapter.pan_by(40, -25)
        self.assertEqual(adapter.pan, (67, -38))
        self.assertEqual(canvas.moves, [("all", 40, -25)])
        self.assertEqual(adapter.hit_test(x + 40, y - 25), cell)


if __name__ == "__main__":
    unittest.main()
