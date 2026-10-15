"""R5.7 headless certification: geometric selection and atomic transforms."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import RuleError
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.map_authoring import MapStudio
from drawtemp.studio.map_selection import (
    lasso_selection, rectangle_selection, union_selection,
)


class SelectionTransformTests(unittest.TestCase):
    def setUp(self):
        self.studio = MapStudio.reference()
        self.studio.create("r57_village", "Village R5.7", 14, 14)

    def paint_shape(self):
        self.studio.paint([(3, 3)], "surface:stone")
        self.studio.paint([(4, 3)], "surface:sand")
        self.studio.paint([(3, 4)], "feature:tree")
        self.studio.paint([(3, 4)], "goal")
        return [(3, 3), (4, 3), (3, 4)]

    def tile(self, pos):
        return next((t for t in self.studio.mission()["board"]["tiles"]
                     if tuple(t["pos"]) == pos), None)

    def test_rectangle_lasso_and_additive_disjoint_selection(self):
        data = self.studio.snapshot()["content"]
        mid = self.studio.mission_id
        self.assertEqual(rectangle_selection(data, mid, (3, 4), (2, 3)),
                         ((2, 3), (3, 3), (2, 4), (3, 4)))
        selected = lasso_selection(data, mid,
                                   [(2, 2), (6, 2), (6, 6), (2, 6), (2, 2)])
        self.assertIn((4, 4), selected)
        self.assertIn((2, 2), selected)
        self.assertNotIn((1, 1), selected)
        line = lasso_selection(data, mid, [(2, 2), (5, 2)])
        self.assertEqual(line, ((2, 2), (3, 2), (4, 2), (5, 2)))
        combined = union_selection(data, mid, [(0, 0)], [(13, 13), (0, 0)])
        self.assertEqual(combined, ((0, 0), (13, 13)))
        self.assertEqual(self.studio.select_rectangle((0, 0), (0, 0),
                          existing=[(12, 12)], additive=True),
                         ((0, 0), (12, 12)))

    def test_copy_paste_snapshot_and_one_undo_for_multiple_tiles(self):
        region = self.paint_shape()
        copied = self.studio.copy_region(region)
        original_clip = deepcopy(copied)
        baseline = self.studio.snapshot()
        preview = self.studio.preview_region(operation="paste", anchor=(8, 8))
        self.assertEqual(baseline, self.studio.snapshot())
        self.assertEqual(len(preview.preview_cells), 3)
        self.studio.commit_region(preview)
        self.assertEqual(self.tile((8, 8))["surface"], "stone")
        self.assertEqual(self.tile((9, 8))["surface"], "sand")
        self.assertEqual(self.tile((8, 9))["feature"], "tree")
        self.assertIn([8, 9], self.studio.mission()["goal"])
        self.assertEqual(copied, original_clip)
        self.studio.undo()
        self.assertIsNone(self.tile((8, 8)))
        self.assertNotIn([8, 9], self.studio.mission()["goal"])
        self.studio.redo()
        self.assertIn([8, 9], self.studio.mission()["goal"])

    def test_in_place_rotate_and_mirrors_with_sparse_terrain_goals(self):
        region = self.paint_shape()
        self.studio.transform_region(region, operation="rotate_cw")
        self.assertEqual(self.tile((4, 3))["surface"], "stone")
        self.assertEqual(self.tile((4, 4))["surface"], "sand")
        self.assertEqual(self.tile((3, 3))["feature"], "tree")
        self.assertIn([3, 3], self.studio.mission()["goal"])
        self.studio.undo()
        self.assertEqual(self.tile((3, 3))["surface"], "stone")
        self.studio.transform_region(region, operation="mirror_x")
        self.assertEqual(self.tile((4, 3))["surface"], "stone")
        self.assertEqual(self.tile((3, 3))["surface"], "sand")
        self.assertIn([4, 4], self.studio.mission()["goal"])
        self.studio.undo()
        self.studio.transform_region(region, operation="mirror_y")
        self.assertEqual(self.tile((3, 4))["surface"], "stone")
        self.assertEqual(self.tile((4, 4))["surface"], "sand")
        self.assertIn([3, 3], self.studio.mission()["goal"])

    def test_move_overlapping_region_and_duplicate_without_erasing_original(self):
        region = self.paint_shape()
        rev = self.studio.authoring.revision
        preview = self.studio.preview_region(region, operation="move", anchor=(4, 3))
        self.assertEqual(rev, self.studio.authoring.revision)
        self.studio.commit_region(preview)
        self.assertEqual(self.studio.authoring.revision, rev + 1)
        self.assertIsNone(self.tile((3, 3)))
        self.assertEqual(self.tile((4, 3))["surface"], "stone")
        self.assertEqual(self.tile((5, 3))["surface"], "sand")
        self.assertIn([4, 4], self.studio.mission()["goal"])
        self.studio.undo()
        self.studio.transform_region(region, operation="duplicate", anchor=(7, 7))
        self.assertEqual(self.tile((3, 3))["surface"], "stone")
        self.assertEqual(self.tile((7, 7))["surface"], "stone")
        self.assertIn([7, 8], self.studio.mission()["goal"])

    def test_stale_preview_undo_aba_and_cross_map_are_rejected(self):
        region = self.paint_shape()
        preview = self.studio.preview_region(region, operation="duplicate",
                                             anchor=(7, 7))
        self.studio.paint([(9, 9)], "surface:dirt")
        self.studio.undo()
        before = self.studio.snapshot()
        with self.assertRaises(AuthoringError) as err:
            self.studio.commit_region(preview)
        self.assertEqual(err.exception.code, "stale_revision")
        self.assertEqual(before, self.studio.snapshot())
        preview = self.studio.preview_region(region, operation="duplicate",
                                             anchor=(7, 7))
        self.studio.select_map(self.studio.map_ids()[0])
        with self.assertRaises(AuthoringError):
            self.studio.commit_region(preview)

    def test_bounds_collision_protection_and_locks_are_atomic(self):
        region = self.paint_shape()
        before = self.studio.snapshot()
        for op, anchor in (("duplicate", (13, 13)), ("move", (13, 13)),
                           ("duplicate", (3, 3))):
            with self.subTest(op=op, anchor=anchor), self.assertRaises(AuthoringError):
                self.studio.preview_region(region, operation=op, anchor=anchor)
        self.assertEqual(before, self.studio.snapshot())
        self.studio.paint([(9, 9)], "surface:water")
        before = self.studio.snapshot()
        with self.assertRaises(AuthoringError):
            self.studio.preview_region(region, operation="duplicate", anchor=(9, 9))
        self.assertEqual(before, self.studio.snapshot())
        self.studio.layers.set_locked(self.studio.mission_id, "Terrain", True)
        with self.assertRaises(AuthoringError):
            self.studio.preview_region(region, operation="move", anchor=(7, 7))
        self.assertEqual(before, self.studio.snapshot())

    def test_building_and_entity_identity_cannot_be_silently_cloned(self):
        self.studio.structure("Maison", (6, 5))
        before = self.studio.snapshot()
        with self.assertRaises((AuthoringError, RuleError)):
            self.studio.preview_region([(6, 5)], operation="duplicate", anchor=(9, 9))
        with self.assertRaises(RuleError):
            self.studio.copy_region([(6, 5)])
        self.assertEqual(before, self.studio.snapshot())
        actors = self.studio.mission()["units"]
        pos = tuple(actors[0]["pos"])
        with self.assertRaises(RuleError):
            self.studio.copy_region([pos])
        with self.assertRaises(AuthoringError):
            self.studio.preview_region([pos], operation="duplicate", anchor=(7, 7))
        self.assertEqual(before, self.studio.snapshot())

    def test_selected_unit_move_keeps_stable_id_and_replays(self):
        actor = self.studio.mission()["units"][0]
        origin = tuple(actor["pos"])
        target = (origin[0]+1, origin[1])
        before = self.studio.snapshot()
        preview = self.studio.preview_region([origin], operation="move",
                                             anchor=target)
        self.assertEqual(preview.moved_units, (actor["id"],))
        self.studio.commit_region(preview)
        moved = next(u for u in self.studio.mission()["units"] if u["id"] == actor["id"])
        self.assertEqual(tuple(moved["pos"]), target)
        self.studio.undo()
        self.assertEqual(self.studio.snapshot()["content"], before["content"])

    def test_round_trip_saves_only_canonical_content_and_project(self):
        self.paint_shape()
        self.studio.transform_region([(3, 3), (4, 3), (3, 4)],
                                     operation="duplicate", anchor=(7, 7))
        with TemporaryDirectory() as directory:
            path = Path(directory)/"transformed.json"
            self.studio.save_as(path)
            reopened = MapStudio.open(path)
            reopened.select_map("r57_village")
            self.assertEqual(self.studio.mission(), reopened.mission())
            self.assertEqual(self.studio.snapshot()["content"],
                             reopened.snapshot()["content"])
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("transform_preview", text)
            self.assertNotIn("selectionCells", text)


if __name__ == "__main__":
    unittest.main()
