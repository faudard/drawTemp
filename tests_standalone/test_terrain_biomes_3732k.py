"""3.7.32K — connected watercolor biomes and safe cosmetic flora."""
from copy import deepcopy
from dataclasses import replace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.model import Content, RuleError
from sporebound.terrain_autoblend import (
    REGION_STYLES, apply_terrain_plan, biome_feature_at,
    plan_terrain_region, surface_at,
)


class BiomeCompositionTests(unittest.TestCase):
    def setUp(self):
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'biomes_k', 'Biome art gate', 32, 32)
        self.doc = Document(Content.from_dict(data))
        self.mid = 'biomes_k'

    def board(self):
        return Content.from_dict(self.doc.data).missions[self.mid].board

    def plan(self, a=(2, 2), b=(26, 26), **options):
        return self.doc.preview_generated_terrain(
            self.mid, a, b, seed=9421, style='bocage', **options)

    def test_domain_warp_biomes_are_portable_and_multimaterial(self):
        self.assertTrue({'bocage', 'lande', 'vallon'} <= set(REGION_STYLES))
        for style in ('bocage', 'lande', 'vallon'):
            with self.subTest(style=style):
                samples = tuple(surface_at(x, y, seed=9421, style=style)
                                for y in range(-8, 40) for x in range(-8, 40))
                self.assertEqual(samples, tuple(
                    surface_at(x, y, seed=9421, style=style)
                    for y in range(-8, 40) for x in range(-8, 40)))
                self.assertGreaterEqual(len(set(samples)), 2)
                self.assertTrue(set(samples) <=
                                {'grass', 'dirt', 'stone', 'rock', 'sand'})

    def test_chunked_preview_matches_whole_with_flora(self):
        source = deepcopy(self.doc.data)
        whole = plan_terrain_region(source, self.mid, (2, 2), (25, 25),
                                    seed=9421, style='bocage', vegetation=3)
        part = plan_terrain_region(source, self.mid, (8, 9), (17, 20),
                                   seed=9421, style='bocage', vegetation=3)
        self.assertEqual(
            {row for row in whole.changes
             if 8 <= row[0] <= 17 and 9 <= row[1] <= 20},
            set(part.changes))
        self.assertEqual(
            {row for row in whole.decorations
             if 8 <= row[0] <= 17 and 9 <= row[1] <= 20},
            set(part.decorations))
        self.assertGreater(len(whole.decorations), 0)
        self.assertTrue({name for _, _, name in whole.decorations} <=
                        {'tree', 'bush', 'boulder', 'reeds'})

    def test_preview_is_pure_and_undo_redo_includes_flora(self):
        source = deepcopy(self.doc.data)
        before_undo = len(self.doc.undo_stack)
        plan = self.plan(vegetation=3)
        self.assertEqual(self.doc.data, source)
        self.assertEqual(len(self.doc.undo_stack), before_undo)
        changed = self.doc.confirm_generated_terrain(plan)
        unique = {(x, y) for x, y, _ in (*plan.changes, *plan.decorations)}
        self.assertEqual(changed, len(unique))
        self.assertEqual(len(self.doc.undo_stack), before_undo + 1)
        self.assertTrue(any(t.feature for t in self.board().tiles.values()))
        committed = deepcopy(self.doc.data)
        self.doc.undo()
        self.assertEqual(self.doc.data, source)
        self.doc.redo()
        self.assertEqual(self.doc.data, committed)
        self.assertEqual(Content.from_dict(committed).to_dict(), committed)

    def test_protected_rivers_bridges_props_relief_and_units(self):
        self.doc.paint_many(self.mid, [(6, 6)], 'surface:water')
        self.doc.paint_many(self.mid, [(7, 6)], 'surface:bridge')
        self.doc.paint_many(self.mid, [(8, 6)], 'feature:tree')
        self.doc.paint_many(self.mid, [(9, 6)], 'height:2')
        self.doc.paint_many(self.mid, [(10, 6)], 'surface:rock')
        self.doc.paint_many(self.mid, [(10, 6)], 'cover:30')
        original = {point: self.board().tile(point)
                    for point in ((6, 6), (7, 6), (8, 6),
                                  (9, 6), (10, 6))}
        plan = self.plan(vegetation=3)
        affected = {(x, y) for x, y, _ in
                    (*plan.changes, *plan.decorations)}
        self.assertFalse(affected.intersection(original))
        self.doc.confirm_generated_terrain(plan)
        self.assertEqual({cell: self.board().tile(cell) for cell in original},
                         original)

    def test_disable_flora_is_backwards_compatible(self):
        plan = self.plan(vegetation=0)
        self.assertEqual(plan.decorations, ())
        self.assertEqual(plan.vegetation, 0)
        self.assertEqual(biome_feature_at(1, 2, vegetation=0), '')
        legacy = self.doc.preview_generated_terrain(
            self.mid, (2, 2), (26, 26), seed=9421, style='prairie')
        self.assertEqual(legacy.decorations, ())

    def test_stale_and_forged_foliage_cannot_commit(self):
        before = deepcopy(self.doc.data)
        plan = self.plan(vegetation=3)
        bad = replace(plan, decorations=((8, 8, 'bridge'),))
        with self.assertRaises(RuleError):
            apply_terrain_plan(self.doc.data, bad)
        self.assertEqual(self.doc.data, before)
        for vegetation in (-1, 4, True, 1.5):
            with self.subTest(vegetation=vegetation), self.assertRaises(RuleError):
                self.plan(vegetation=vegetation)
        self.doc.paint_many(self.mid, [(0, 0)], 'surface:dirt')
        snapshot = deepcopy(self.doc.data)
        with self.assertRaises(RuleError):
            self.doc.confirm_generated_terrain(plan)
        self.assertEqual(self.doc.data, snapshot)


if __name__ == '__main__':
    unittest.main()
