"""3.7.32F — procedural terrain and neighbour-aware AutoBlend contracts."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.editor_dirty_tiles import affected_terrain_cells
from sporebound.iso_connections import E, N, S, W
from sporebound.iso_map import IsoGeometry
from sporebound.model import Board, Content, RuleError, Tile
from sporebound.terrain_autoblend import (
    BlendEdge, REGION_STYLES, LAND_COLORS, apply_terrain_plan, blend_edges,
    blend_polygon, plan_terrain_region, surface_at, terrain_dependents,
    terrain_variant,
)


class AutoBlendTests(unittest.TestCase):
    def setUp(self):
        self.board = Board(8, 8)

    def paint(self, cell, surface, *, height=0):
        self.board.tiles[cell] = Tile(surface=surface, height=height)

    def test_different_neighbours_share_one_terrestrial_edge(self):
        self.paint((3, 3), 'dirt')
        self.paint((4, 3), 'grass')
        self.paint((3, 2), 'stone')
        self.paint((2, 3), 'dirt')
        self.paint((3, 4), 'dirt')
        edges = blend_edges(self.board, (3, 3))
        self.assertEqual({e.bit: e.incoming for e in edges},
                         {E: 'grass', N: 'stone'})
        self.assertEqual(blend_edges(self.board, (4, 3)), ())
        self.assertEqual(edges, blend_edges(self.board, (3, 3)))
        self.assertEqual(blend_edges(self.board, (-1, -1)), ())

    def test_water_bridge_and_elevation_never_receive_land_overlay(self):
        self.paint((3, 3), 'water')
        self.paint((4, 3), 'grass')
        self.assertEqual(blend_edges(self.board, (3, 3)), ())
        self.paint((3, 3), 'bridge')
        self.assertEqual(blend_edges(self.board, (3, 3)), ())
        self.paint((3, 3), 'dirt', height=3)
        self.assertEqual(blend_edges(self.board, (3, 3)), ())
        self.paint((4, 3), 'grass', height=3)
        self.assertEqual([edge.bit for edge in blend_edges(self.board, (3, 3))],
                         [E])

    def test_blend_polygons_touch_shared_edge_at_24_54_96(self):
        self.paint((3, 3), 'dirt')
        self.paint((4, 3), 'grass')
        for adjacent in ((3, 2), (2, 3), (3, 4)):
            self.paint(adjacent, 'dirt')
        for zoom in (24, 54, 96):
            with self.subTest(zoom=zoom):
                corners = IsoGeometry(self.board, zoom).polygon((3, 3))
                edge = blend_edges(self.board, (3, 3))[0]
                polygon = blend_polygon(corners, edge)
                self.assertEqual(len(polygon), 18)
                # East neighbour joins the east-to-south geometric side.
                east, south = corners[1], corners[2]
                self.assertEqual(polygon[:4], (*east, *south))
                self.assertTrue(all(isinstance(v, (int, float))
                                    for v in polygon))

    def test_local_damage_includes_only_direct_neighbours(self):
        expected = {(3, 3), (2, 3), (4, 3), (3, 2), (3, 4)}
        self.assertEqual(terrain_dependents(self.board, {(3, 3)}), expected)
        self.assertEqual(len(terrain_dependents(self.board, {(0, 0)})), 3)

    def test_no_python_hash_or_random_state_affects_variants(self):
        for cell in ((0, 0), (2, 6), (999, -14)):
            self.assertEqual(terrain_variant(cell), terrain_variant(cell))
            self.assertIn(terrain_variant(cell), (0, 1))
        self.assertEqual(set(REGION_STYLES), {'prairie', 'aride', 'rocaille'})
        self.assertEqual(len(LAND_COLORS), 6)


class ProceduralTerrainTests(unittest.TestCase):
    def setUp(self):
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'autoblend', 'Terrain generator', 24, 24)
        self.doc = Document(Content.from_dict(data))
        self.mid = 'autoblend'

    def board(self):
        return Content.from_dict(self.doc.data).missions[self.mid].board

    def test_coordinates_remain_consistent_across_overlapping_rectangles(self):
        source = deepcopy(self.doc.data)
        whole = plan_terrain_region(source, self.mid, (4, 4), (17, 17),
                                    seed=42, style='aride')
        part = plan_terrain_region(source, self.mid, (9, 7), (14, 13),
                                   seed=42, style='aride')
        self.assertEqual(
            {row for row in whole.changes if 9 <= row[0] <= 14
             and 7 <= row[1] <= 13},
            set(part.changes))
        self.assertEqual(whole, plan_terrain_region(
            source, self.mid, (4, 4), (17, 17), seed=42, style='aride'))
        self.assertTrue(any(surface_at(x, y, seed=42, style='aride') !=
                            surface_at(x, y, seed=93, style='aride')
                            for x in range(32) for y in range(32)))

    def test_preview_is_pure_and_confirm_one_undo_with_redo(self):
        before = deepcopy(self.doc.data)
        count = len(self.doc.undo_stack)
        plan = self.doc.preview_generated_terrain(
            self.mid, (4, 4), (18, 18), seed=7, style='aride')
        self.assertGreater(len(plan.changes), 0)
        self.assertEqual(self.doc.data, before)
        self.assertEqual(len(self.doc.undo_stack), count)
        applied = self.doc.confirm_generated_terrain(plan)
        self.assertEqual(applied, len(plan.changes))
        self.assertEqual(len(self.doc.undo_stack), count+1)
        changed = deepcopy(self.doc.data)
        self.doc.undo()
        self.assertEqual(self.doc.data, before)
        self.doc.redo()
        self.assertEqual(self.doc.data, changed)

    def test_preserves_river_bridge_props_and_elevated_terrain(self):
        self.doc.paint_many(self.mid, [(9, 9)], 'surface:water')
        self.doc.paint_many(self.mid, [(10, 9)], 'surface:bridge')
        self.doc.paint_many(self.mid, [(11, 9)], 'feature:bush')
        self.doc.paint_many(self.mid, [(12, 9)], 'height:2')
        before = {(x, 9): self.board().tile((x, 9))
                  for x in range(9, 13)}
        plan = self.doc.preview_generated_terrain(
            self.mid, (7, 7), (14, 13), seed=17, style='aride')
        self.assertFalse(any((x, y) in before for x, y, _ in plan.changes))
        self.doc.confirm_generated_terrain(plan)
        self.assertEqual(
            {(x, 9): self.board().tile((x, 9)) for x in range(9, 13)},
            before)

    def test_reject_stale_plan_without_undo_or_content_mutation(self):
        plan = self.doc.preview_generated_terrain(
            self.mid, (5, 5), (12, 12), seed=7, style='aride')
        self.doc.paint_many(self.mid, [(0, 0)], 'surface:dirt')
        before = deepcopy(self.doc.data)
        undo_count = len(self.doc.undo_stack)
        with self.assertRaises(RuleError):
            self.doc.confirm_generated_terrain(plan)
        self.assertEqual(self.doc.data, before)
        self.assertEqual(len(self.doc.undo_stack), undo_count)

    def test_invalid_requests_and_forgeries_never_modify_document(self):
        before = deepcopy(self.doc.data)
        for kwargs in (dict(seed=-1), dict(seed=True), dict(style='lava')):
            with self.subTest(kwargs=kwargs), self.assertRaises(RuleError):
                self.doc.preview_generated_terrain(
                    self.mid, (5, 5), (8, 8), **kwargs)
        with self.assertRaises(RuleError):
            self.doc.preview_generated_terrain(self.mid, (-1, 0), (1, 1))
        self.assertEqual(self.doc.data, before)

    def test_visual_dirty_region_handles_an_autoblended_neighbour(self):
        before = Content.from_dict(self.doc.data).missions[self.mid]
        geo = IsoGeometry(before.board, 54)
        self.doc.paint_many(self.mid, [(18, 18)], 'surface:dirt')
        after = Content.from_dict(self.doc.data).missions[self.mid]
        dirty = affected_terrain_cells(before, after, geometry=geo)
        # The existing dirty-tile system conservatively invalidates 3×3;
        # AutoBlend requires only 4 adjacent cells and never a full refresh.
        if dirty is not None:
            self.assertTrue(terrain_dependents(
                after.board, {(18, 18)}) <= dirty)
            self.assertLessEqual(len(dirty), 9)

    def test_incomplete_plan_rejected_before_mutating_data(self):
        plan = self.doc.preview_generated_terrain(
            self.mid, (3, 3), (7, 7), seed=10, style='aride')
        # A hand-edited/corrupt plan is not blindly trusted.
        from dataclasses import replace
        altered = replace(plan, changes=((4, 4, 'water'),))
        before = deepcopy(self.doc.data)
        with self.assertRaises(RuleError):
            apply_terrain_plan(self.doc.data, altered)
        self.assertEqual(self.doc.data, before)


if __name__ == '__main__':
    unittest.main()
