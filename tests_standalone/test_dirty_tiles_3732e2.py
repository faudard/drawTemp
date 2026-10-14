"""3.7.32E2 planner covers stable geometry with actors and decorations."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.editor_dirty_tiles import affected_terrain_cells
from sporebound.iso_architecture import architecture_instances
from sporebound.iso_map import IsoGeometry
from sporebound.iso_structures import place_structure
from sporebound.model import Content


class OcclusionDirtyTilePlannerTests(unittest.TestCase):
    def fixture(self, *, size=65, house=True):
        mid = "occlusion"
        raw = add_blank_mission(
            Content.load(DEFAULT_CONTENT).to_dict(),
            mid, "Test architecture", size, size)
        if house:
            raw = place_structure(raw, mid, "Maison", (15, 15))
        doc = Document(Content.from_dict(raw))
        before = Content.from_dict(doc.data).missions[mid]
        geo = IsoGeometry(before.board, 54)
        geo.architecture_instances = architecture_instances(
            before.board, before.structures)
        return doc, before, geo

    def test_near_actor_dirty_region_supported(self):
        doc, before, geo = self.fixture(house=False)
        doc.paint_many("occlusion", [(2, 63)], "surface:water")
        after = Content.from_dict(doc.data).missions["occlusion"]
        self.assertEqual(len(affected_terrain_cells(
            before, after, geometry=geo)), 9)

    def test_near_roof_and_tall_prop_stable(self):
        doc, before, geo = self.fixture()
        doc.paint_many("occlusion", [(14, 15)], "feature:tree")
        after = Content.from_dict(doc.data).missions["occlusion"]
        self.assertEqual(len(affected_terrain_cells(
            before, after, geometry=geo)), 9)
        self.assertEqual(architecture_instances(
            before.board, before.structures),
            architecture_instances(after.board, after.structures))

    def test_building_identity_change_and_actor_move_force_full(self):
        doc, before, geo = self.fixture()
        doc.paint_many("occlusion", [(14, 15)], "surface:water")
        after = Content.from_dict(doc.data).missions["occlusion"]
        tampered = deepcopy(after)
        tampered.structures[0]["anchor"] = [10, 10]
        self.assertIsNone(affected_terrain_cells(
            before, tampered, geometry=geo))
        actor_moved = deepcopy(after)
        actor_moved.units[0].pos = (2, 2)
        self.assertIsNone(affected_terrain_cells(
            before, actor_moved, geometry=geo))
        height = deepcopy(after)
        height.board.tiles[(14, 15)].height = 1
        self.assertIsNone(affected_terrain_cells(
            before, height, geometry=geo))

    def test_architecture_identity_revalidation(self):
        doc, before, geo = self.fixture()
        doc.paint_many("occlusion", [(14, 15)], "surface:water")
        after = Content.from_dict(doc.data).missions["occlusion"]
        geo.architecture_instances = ()
        self.assertIsNone(affected_terrain_cells(
            before, after, geometry=geo))
        # A marker exists only after a full architecture pass, never inferred
        # from a hidden copy of the authoring document.
        self.assertEqual(len(architecture_instances(
            after.board, after.structures)), 1)


if __name__ == "__main__":
    unittest.main()
