"""R7.9 pure projections: engine owns reachability/LOS/cost/forecast."""
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.model import Content, RuleError
from sporebound.presentation import Camera
from sporebound.iso_map import IsoGeometry
from sporebound.iso_battle_view import viewport_shift
from sporebound.player_action_preview import (
    action_preview, preview_screen_geometry,
)


class ActionPreviewR7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)

    def setUp(self):
        self.battle = Battle(self.content, "garden", seed=77)
        actor = next(u for u in self.battle.units
                     if u.team == "player" and u.alive)
        # Isolate UI projections without writing a fabricated battle replay.
        self.battle.deploying = False
        self.battle.active_id = actor.id
        self.actor = actor
        self.cell = tuple(actor.pos)

    def test_deploy_enemy_and_terminal_phases_have_no_engine_commit(self):
        before = self.battle.digest()
        self.battle.deploying = True
        p = action_preview(self.battle, "deploy", self.cell)
        self.assertEqual(p.status, "conditional")
        self.assertFalse(p.path)
        self.battle.deploying = False
        self.assertEqual(self.battle.digest(), before)

        enemy = next(u for u in self.battle.units if u.team == "enemy")
        self.battle.active_id = enemy.id
        self.assertEqual(action_preview(self.battle, "move", self.cell).status,
                         "inactive")
        self.battle.active_id = self.actor.id
        self.assertEqual(action_preview(
            self.battle, "move", self.cell).status, "blocked")

    def test_reachable_move_uses_exact_engine_path_cost_and_risks(self):
        moves = self.battle.reachable(self.actor)
        targets = [cell for cell in moves if cell != self.cell]
        self.assertTrue(targets, "Reference map should provide a walkable destination")
        target = sorted(targets)[0]
        cost, path = moves[target]
        before = self.battle.digest()
        first = action_preview(self.battle, "move", target)
        self.assertEqual(first.status, "available")
        self.assertEqual(first.path, tuple(map(tuple, path)))
        self.assertEqual(first.cost, cost)
        self.assertEqual(first.destination, target)
        self.assertEqual(first, action_preview(self.battle, "move", target))
        self.assertEqual(self.battle.digest(), before)

        with patch.object(self.battle, "movement_threats",
                          return_value=[{"kind": "engagement",
                                         "unit": "enemy", "cell": target}]):
            danger = action_preview(self.battle, "move", target)
        self.assertIn("engagement", " ".join(danger.details))
        self.assertIn("possible", " ".join(danger.details))

    def test_forecast_is_authoritative_and_blocked_los_is_not_approved(self):
        before = self.battle.digest()
        with patch.object(self.battle, "forecast", return_value=[
            {"unit": "enemy", "kind": "damage", "chance": 0.65,
             "amount": 12, "redirected_to": "guard"}
        ]) as forecast:
            p = action_preview(self.battle, "attack", self.cell)
        forecast.assert_called_once_with("attack", self.cell, self.actor)
        self.assertEqual(p.status, "available")
        self.assertEqual(p.path, (self.cell, self.cell))
        self.assertIn("LOS", " ".join(p.details))
        self.assertIn("65%", " ".join(p.details))
        self.assertIn("12", " ".join(p.details))
        self.assertIn("guard", " ".join(p.details))
        with patch.object(self.battle, "forecast",
                          side_effect=RuleError("Line of sight blocked")):
            rejected = action_preview(self.battle, "attack", self.cell)
        self.assertEqual(rejected.status, "blocked")
        self.assertIn("Line of sight blocked", " ".join(rejected.details))
        self.assertEqual(self.battle.digest(), before)

    def test_interaction_checks_existing_object_without_predicting_effects(self):
        obj = {"id": "testgate", "kind": "door", "pos": list(self.cell),
               "open": False}
        self.battle.mission.objects.append(obj)
        with patch.object(self.battle, "can_interact", return_value=False):
            rejected = action_preview(self.battle, "object:testgate", self.cell)
        self.assertEqual(rejected.status, "blocked")
        with patch.object(self.battle, "can_interact", return_value=True) as check:
            valid = action_preview(self.battle, "object:testgate", self.cell)
        check.assert_called_once_with(self.actor, "testgate")
        self.assertEqual(valid.status, "available")
        self.assertTrue(any("pas simulées" in text for text in valid.details))
        self.assertEqual(action_preview(self.battle, "object:unknown", self.cell).status,
                         "blocked")

    def test_multilevel_forecasts_and_paths_use_engine_records(self):
        start = (0, *self.cell)
        target = (1, min(self.cell[0]+1, self.battle.board.width-1), self.cell[1])
        with patch.object(self.battle, "level_reachable", return_value={
            target: (4, [start, target])
        }):
            preview = action_preview(self.battle, "level_move", target[1:],
                                     target_level=1)
        self.assertEqual(preview.cost, 4)
        self.assertEqual(preview.levels, (0, 1))
        self.assertEqual(preview.path, (start[1:], target[1:]))
        self.assertEqual(preview.status, "available")
        with patch.object(self.battle, "vertical_forecast", return_value={
            "unit": "enemy", "kind": "vertical_attack",
            "chance": .8, "amount": 8
        }):
            shot = action_preview(self.battle, "level_attack", target[1:],
                                  target_level=1)
        self.assertEqual(shot.status, "available")
        self.assertIn("80%", " ".join(shot.details))

    def test_iso_and_2d_previews_share_tile_centers_at_three_zooms(self):
        target = self.cell
        for size in (24, 54, 96):
            cam = Camera(size, 7, 11)
            preview = action_preview(self.battle, "move", target)
            points, marker = preview_screen_geometry(preview, cam)
            self.assertEqual(marker, (7 + (target[0]+.5)*size,
                                      11 + (target[1]+.5)*size))
            self.assertEqual(points, ())
            geometry = IsoGeometry(self.battle.board, size)
            shift = viewport_shift(geometry, cam, (900, 680))
            _points, marker = preview_screen_geometry(
                preview, cam, iso_geometry=geometry, shift=shift)
            center = geometry.center(target)
            self.assertEqual(marker, (center[0]+shift[0], center[1]+shift[1]))

    def test_invalid_target_fails_closed_without_any_mutation(self):
        digest = self.battle.digest()
        for cell in ((-1, 0), (self.battle.board.width, 0),
                     ("1", 1), (0,)):
            with self.assertRaises(ValueError):
                action_preview(self.battle, "move", cell)
        with self.assertRaises(ValueError):
            action_preview(self.battle, "level_move", self.cell,
                           target_level="1")
        self.assertEqual(self.battle.digest(), digest)


if __name__ == "__main__":
    unittest.main()
