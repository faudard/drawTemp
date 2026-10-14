"""Regression checks for Jeanne's narrative-to-2.5D presentation bridge."""
from copy import deepcopy
from pathlib import Path
from unittest import TestCase, mock

from sporebound.exploration_iso_view import (
    IsoExplorationCanvas, exploration_iso_pick, exploration_iso_shift,
    exploration_visual_board)
from sporebound.iso_map import IsoGeometry
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "sporebound" / "content" / "jeanne.json"
PROJECT = ROOT / "sporebound" / "content" / "jeanne.game.json"


class FakeCanvas:
    def __init__(self):
        self.calls = []

    def configure(self, **kwargs):
        self.calls.append(("configure", kwargs))

    def move(self, *args):
        self.calls.append(("move", args))

    def create_oval(self, *args, **kwargs):
        self.calls.append(("oval", args))

    def create_text(self, *args, **kwargs):
        self.calls.append(("text", kwargs.get("text")))


class ExplorationIsoViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        content = Content.load(CONTENT)
        project = GameProject.load(PROJECT, content)
        cls.stage = GameSession.new(content, project, "jeanne").exploration_state()

    def test_visual_board_is_transient_and_matches_narrative_coordinates(self):
        stage = deepcopy(self.stage)
        before = deepcopy(stage)
        board = exploration_visual_board(stage)
        self.assertEqual((board.width, board.height),
                         (stage["width"], stage["height"]))
        for cell in board.cells():
            self.assertEqual(board.tile(cell).blocked,
                             cell in {tuple(p) for p in stage["blocked"]})
        self.assertEqual(stage, before)
        self.assertEqual(board.tile(tuple(stage["position"])).surface, "grass")

    def test_iso_picking_uses_canonical_geometry(self):
        board = exploration_visual_board(self.stage)
        geo = IsoGeometry(board, 28)
        shift = exploration_iso_shift(geo, (690, 495))
        for cell in board.cells():
            cx, cy = geo.center(cell)
            self.assertEqual(exploration_iso_pick(
                geo, shift, cx + shift[0], cy + shift[1]), cell)
        self.assertIsNone(exploration_iso_pick(geo, shift, -999, -999))

    def test_view_delegates_to_shared_renderer_and_keeps_state_immutable(self):
        stage = deepcopy(self.stage)
        before = deepcopy(stage)
        canvas = FakeCanvas()
        geometry = IsoGeometry(exploration_visual_board(stage), 28)
        with mock.patch("sporebound.exploration_iso_view.render_isometric",
                        return_value=geometry) as shared:
            view = IsoExplorationCanvas(canvas)
            self.assertIs(view.draw(stage), geometry)
        self.assertEqual(shared.call_count, 1)
        args, kwargs = shared.call_args
        self.assertEqual([u.name for u in args[3]], ["Jeanne"])
        self.assertEqual(kwargs["cell_size"], 28)
        self.assertTrue(kwargs["omit_architecture"])
        self.assertTrue(kwargs["layers"]["Terrain"])
        self.assertIsNotNone(kwargs["actor_atlas"])
        self.assertIsNotNone(kwargs["atlas"])
        self.assertEqual(view.hit_test(*view._center(stage["position"])),
                         tuple(stage["position"]))
        self.assertIn("oval", [call[0] for call in canvas.calls])
        self.assertEqual(stage, before)


if __name__ == "__main__":
    import unittest
    unittest.main()
