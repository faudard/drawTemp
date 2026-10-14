"""3.7.32L — connected rivers, bridges, roads, relief and safe authoring."""
from copy import deepcopy
from dataclasses import replace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.model import Content, RuleError
from sporebound.terrain_landscape import (
    NaturalMapPlan, apply_natural_map, plan_natural_map,
)


class NaturalMapTests(unittest.TestCase):
    def setUp(self):
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'landscape_l', 'Natural map', 32, 32)
        self.doc = Document(Content.from_dict(data))
        self.mid = 'landscape_l'

    def preview(self, seed=42, style='bocage', vegetation=2,
                start=(3, 3), end=(26, 26)):
        return self.doc.preview_natural_map(
            self.mid, start, end, seed=seed, style=style,
            vegetation=vegetation)

    @staticmethod
    def is_connected(path):
        return all(abs(a[0]-b[0]) + abs(a[1]-b[1]) == 1
                   for a, b in zip(path, path[1:]))

    def test_deterministic_continuous_hydrology_and_crossing(self):
        baseline = deepcopy(self.doc.data)
        for seed in (42, 43, 9982):
            with self.subTest(seed=seed):
                plan = self.preview(seed=seed)
                self.assertIsInstance(plan, NaturalMapPlan)
                self.assertEqual(plan, self.preview(seed=seed))
                self.assertEqual(plan.source_sha256,
                                 self.preview(seed=seed).source_sha256)
                self.assertTrue(self.is_connected(plan.river))
                self.assertTrue(self.is_connected(plan.road))
                self.assertGreater(len(plan.river), 20)
                self.assertGreater(len(plan.road), 20)
                river = set(plan.river)
                road = set(plan.road)
                crossings = river & road
                self.assertTrue(crossings)
                changes = {(x, y): (surface, height, blocked, feature)
                           for x, y, surface, height, blocked, feature
                           in plan.changes}
                for point in crossings:
                    self.assertEqual(changes[point][:3], ('bridge', 0, False))
                for point in river - crossings:
                    self.assertEqual(changes[point][:3], ('water', 0, True))
                for point in road - crossings:
                    surface, height, blocked, feature = changes[point]
                    self.assertEqual((surface, height, blocked, feature),
                                     ('dirt', 0, False, ''))
        self.assertEqual(self.doc.data, baseline)

    def test_landscape_undo_redo_and_replay_serialization(self):
        original = deepcopy(self.doc.data)
        undo_count = len(self.doc.undo_stack)
        plan = self.preview()
        self.assertEqual(undo_count, len(self.doc.undo_stack))
        self.assertEqual(self.doc.confirm_natural_map(plan), len(plan.changes))
        self.assertEqual(len(self.doc.undo_stack), undo_count + 1)
        committed = deepcopy(self.doc.data)
        self.assertEqual(Content.from_dict(committed).to_dict(), committed)
        board = Content.from_dict(committed).missions[self.mid].board
        self.assertTrue(any(board.tile(p).surface == 'water'
                            for p in set(plan.river) - set(plan.road)))
        self.assertTrue(all(board.tile(p).surface in ('bridge', 'dirt')
                            and not board.tile(p).blocked for p in plan.road))
        self.doc.undo()
        self.assertEqual(self.doc.data, original)
        self.doc.redo()
        self.assertEqual(self.doc.data, committed)

    def test_existing_authored_cells_are_not_repainted(self):
        # Safely outside the central river/road corridor.
        self.doc.paint_many(self.mid, [(3, 3)], 'surface:water')
        self.doc.paint_many(self.mid, [(4, 4)], 'surface:cobble')
        self.doc.paint_many(self.mid, [(5, 5)], 'feature:bush')
        self.doc.paint_many(self.mid, [(6, 6)], 'height:2')
        cells = {(3, 3), (4, 4), (5, 5), (6, 6)}
        before = Content.from_dict(self.doc.data).missions[self.mid].board
        originals = {point: before.tile(point) for point in cells}
        plan = self.preview()
        self.assertFalse(cells.intersection(plan.changed_cells))
        self.doc.confirm_natural_map(plan)
        after = Content.from_dict(self.doc.data).missions[self.mid].board
        self.assertEqual({point: after.tile(point) for point in cells},
                         originals)

    def test_protected_crossing_rejected_without_partial_edits(self):
        path = self.preview().river
        # A protected authored prop on the water corridor cannot be removed.
        p = path[len(path)//3]
        self.doc.paint_many(self.mid, [p], 'feature:tree')
        state = deepcopy(self.doc.data)
        undo = len(self.doc.undo_stack)
        with self.assertRaises(RuleError):
            self.preview()
        self.assertEqual(self.doc.data, state)
        self.assertEqual(len(self.doc.undo_stack), undo)

    def test_stale_plan_and_forgery_refused(self):
        plan = self.preview()
        corrupted = replace(plan, changes=plan.changes[:-1])
        with self.assertRaises(RuleError):
            apply_natural_map(self.doc.data, corrupted)
        state = deepcopy(self.doc.data)
        self.assertEqual(self.doc.data, state)
        self.doc.paint_many(self.mid, [(0, 0)], 'surface:dirt')
        after = deepcopy(self.doc.data)
        with self.assertRaises(RuleError):
            self.doc.confirm_natural_map(plan)
        self.assertEqual(self.doc.data, after)

    def test_identical_bytes_after_undo_cannot_reuse_old_preview(self):
        plan = self.preview()
        original = deepcopy(self.doc.data)
        self.doc.paint_many(self.mid, [(0, 0)], 'surface:dirt')
        self.doc.undo()
        self.assertEqual(self.doc.data, original)
        with self.assertRaises(RuleError):
            self.doc.confirm_natural_map(plan)
        self.assertEqual(self.doc.data, original)
        fresh = self.preview()
        self.assertGreater(self.doc.confirm_natural_map(fresh), 0)

    def test_invalid_inputs_and_all_preset_biomes(self):
        for seed in (True, -1, 0x80000000):
            with self.subTest(seed=seed), self.assertRaises(RuleError):
                self.preview(seed=seed)
        for density in (True, -1, 4):
            with self.subTest(density=density), self.assertRaises(RuleError):
                self.preview(vegetation=density)
        for style in ('bocage', 'lande', 'vallon',
                      'prairie', 'aride', 'rocaille'):
            with self.subTest(style=style):
                self.assertTrue(self.preview(style=style).road)
        with self.assertRaises(RuleError):
            self.preview(start=(3, 3), end=(8, 8))
        self.assertEqual(self.doc.undo_stack, [])


if __name__ == '__main__':
    unittest.main()
