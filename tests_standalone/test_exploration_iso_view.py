"""Regression checks for Jeanne's narrative-to-2.5D presentation bridge."""
from copy import deepcopy
from pathlib import Path
from unittest import TestCase, mock

from sporebound.exploration_iso_view import (
    IsoExplorationCanvas, exploration_iso_pick, exploration_iso_shift,
    exploration_visual_board, exploration_visual_cast)
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

    def create_rectangle(self, *args, **kwargs):
        self.calls.append(("rectangle", kwargs.get("tags")))

    def create_polygon(self, *args, **kwargs):
        self.calls.append(("polygon", kwargs.get("tags")))

    def tag_lower(self, *args):
        self.calls.append(("lower", args))


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

    def test_cast_is_visual_only_and_skips_rescued_or_lost_npcs(self):
        stage = deepcopy(self.stage)
        before = deepcopy(stage)
        stage["actors"] = [
            {"id": "a", "name": "Paysanne", "kind": "civilian",
             "status": "active", "pos": (2, 2)},
            {"id": "b", "name": "Sauvee", "kind": "civilian",
             "status": "rescued", "pos": (3, 2)},
            {"id": "c", "name": "Perdue", "kind": "civilian",
             "status": "lost", "pos": (4, 2)},
        ]
        cast = exploration_visual_cast(stage)
        self.assertEqual([unit.id for unit in cast], ["jeanne", "story_a"])
        self.assertEqual(cast[1].pos, (2, 2))
        self.assertNotEqual(stage, before)  # Only the test fixture was edited.
        self.assertEqual(cast[0].team, "player")

    def test_visual_board_is_repeatable_and_clears_character_tiles(self):
        for theme in ("fields", "village", "forest", "stone"):
            stage = deepcopy(self.stage)
            stage["theme"] = theme
            original = deepcopy(stage)
            a = exploration_visual_board(stage)
            b = exploration_visual_board(stage)
            self.assertEqual(a.tiles, b.tiles)
            self.assertEqual(stage, original)
            for actor in stage.get("actors", ()):
                if tuple(actor["pos"]) not in stage["blocked"]:
                    self.assertFalse(a.tile(tuple(actor["pos"])).feature)

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
        self.assertEqual(args[3][0].name, "Jeanne")
        self.assertEqual(len(args[3]), 1 + sum(
            a["status"] == "active" for a in stage.get("actors", ())))
        self.assertEqual(kwargs["cell_size"], 28)
        self.assertTrue(kwargs["omit_architecture"])
        self.assertTrue(kwargs["layers"]["Terrain"])
        self.assertIsNotNone(kwargs["actor_atlas"])
        self.assertIsNotNone(kwargs["atlas"])
        self.assertEqual(view.hit_test(*view._center(stage["position"])),
                         tuple(stage["position"]))
        self.assertIn("oval", [call[0] for call in canvas.calls])
        self.assertIn("polygon", [call[0] for call in canvas.calls])
        self.assertIn("rectangle", [call[0] for call in canvas.calls])
        self.assertEqual(stage, before)


if __name__ == "__main__":
    import unittest
    unittest.main()
