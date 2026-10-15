"""R13.6 Encounter Designer 2.0: canonical edit and transaction gates."""
from __future__ import annotations

from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.r13_encounter_authoring import (
    build_encounter, compare_draft, preview_authoring,
)
from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.model import Board, Content, Mission, RuleError, Unit


def arena():
    return Content({}, {"arena": Mission(
        "arena", "Arena", Board(7, 5), [
            Unit("hero", "Hero", "player", (0, 1)),
            Unit("guard", "Guard", "enemy", (5, 1)),
        ], objective="eliminate",
    )})


class EncounterDesignerR13Tests(unittest.TestCase):
    def test_goal_and_gear_edits_are_real_validated_content(self):
        content = arena()
        before = content.to_dict()
        edits = {
            "objective": "extract", "goal_cells": [[6, 4]],
            "unit_positions": {"hero": [1, 1]},
            "unit_overrides": {"guard": {"weapon": "ranged", "attack_range": 3}},
            "tile_changes": [{"pos": [2, 2], "cover": 50, "height": 1}],
        }
        candidate = build_encounter(content, "arena", edits)
        m = candidate.missions["arena"]
        self.assertEqual(m.objective, "extract")
        self.assertEqual(m.goal, [(6, 4)])
        self.assertEqual(m.units[0].pos, (1, 1))
        self.assertEqual(m.units[1].weapon, "ranged")
        self.assertEqual(m.board.tile((2, 2)).height, 1)
        self.assertEqual(content.to_dict(), before)
        edits["unit_positions"]["hero"] = [2, 2]
        self.assertEqual(m.units[0].pos, (1, 1))
        self.assertEqual(Content.from_dict(candidate.to_dict()).to_dict(),
                         candidate.to_dict())

    def test_rejected_edit_is_atomic_and_catches_collisions(self):
        content = arena()
        before = content.to_dict()
        invalid = [
            {"unit_positions": {"hero": [5, 1]}},  # enemy occupied
            {"unit_positions": {"hero": [200, 3]}},
            {"unit_positions": {"missing": [2, 3]}},
            {"unit_positions": {"hero": [True, 1]}},
            {"goal_cells": [[2, 2], [2, 2]]},
            {"objective": "not_a_rule"},
            {"objective": "extract", "goal_cells": []},
            {"tile_changes": [{"pos": [0, 1], "blocked": True}]},
            {"tile_changes": [{"pos": [3, 3], "height": -1}]},
            {"tile_changes": [{"pos": [3, 3], "blocked": 1}]},
            {"unit_overrides": {"guard": {"name": "bypass"}}},
            {"unit_overrides": {"guard": {"attack_range": "3"}}},
            {"goal_cells": [[3, 3.0]]},
            {"target_ticks": True},
            {"unknown_property": 123},
            {},
        ]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(RuleError):
                build_encounter(content, "arena", item)
        self.assertEqual(content.to_dict(), before)

    def test_objective_change_does_not_fake_comparable_balance(self):
        content = arena()
        report = compare_draft(content, "arena",
                               {"objective": "extract", "goal_cells": [[6, 4]]},
                               seeds=(1, 3), max_commands=16)
        self.assertTrue(report["replays_verified"])
        self.assertTrue(report["objective_changed"])
        self.assertFalse(report["comparison"]["passed"])
        self.assertTrue(report["comparison"]["human_signoff_required"])
        self.assertEqual(report["baseline"]["seeds"], report["candidate"]["seeds"])
        self.assertEqual(content.missions["arena"].objective, "eliminate")
        same_objective = compare_draft(
            content, "arena", {"unit_positions": {"hero": [1, 1]}},
            seeds=(1, 3), max_commands=16)
        self.assertTrue(same_objective["replays_verified"])
        self.assertFalse(same_objective["objective_changed"])
        self.assertTrue(same_objective["comparison"]["authored_inputs_changed"])

    def test_r1_preview_apply_undo_redo_and_stale_gate(self):
        content, project = reference_project()
        studio = AuthoringSession.new(content, project)
        original = studio.snapshot().to_dict()
        edit = {"unit_positions": {"jeanne": [1, 2]}}
        # Use a known, valid in-bounds tile not occupied by fixtures.
        mission = content.missions[MISSION]
        occupied = set().union(*(u.occupied_cells()
                                  for u in mission.units if u.id != "jeanne"))
        free = next((cell for cell in mission.board.cells()
                     if cell not in occupied and
                     not mission.board.tile(cell).blocked and
                     cell not in mission.goal and cell != next(
                         u.pos for u in mission.units if u.id == "jeanne")),
                    None)
        self.assertIsNotNone(free)
        edit["unit_positions"]["jeanne"] = list(free)
        plan = preview_authoring(studio, MISSION, edit)
        self.assertEqual(studio.snapshot().to_dict(), original)
        committed = studio.apply(plan)
        self.assertEqual(committed.kind, "r13-encounter")
        self.assertTrue(committed.snapshot.can_undo)
        self.assertEqual(list(next(u["pos"] for m in
                              committed.snapshot.to_dict()["content"]["missions"]
                              if m["id"] == MISSION for u in m["units"]
                              if u["id"] == "jeanne")), list(free))
        self.assertEqual(studio.undo().snapshot.content,
                         AuthoringSession.new(content, project).snapshot().content)
        self.assertTrue(studio.redo().snapshot.dirty)
        with self.assertRaises(AuthoringError):
            studio.apply(plan)

    def test_invalid_transaction_preserves_canonical_history(self):
        content, project = reference_project()
        studio = AuthoringSession.new(content, project)
        original = studio.snapshot()
        with self.assertRaises(AuthoringError):
            preview_authoring(studio, MISSION,
                              {"unit_positions": {"jeanne": [999, 999]}})
        self.assertEqual(studio.snapshot(), original)


if __name__ == "__main__":
    unittest.main()
