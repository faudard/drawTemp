"""R5.4/5.5 headless smart brush, AutoBlend and palette regression gates."""
from copy import deepcopy
import unittest

from drawtemp.core import Content
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.map_authoring import MapStudio
from drawtemp.studio.map_palette import CATALOG, IDS, MIME_BRUSH, find_cards, require_brush
from drawtemp.render.iso_scene import scene_from_mission, render_items, Camera


class SmartPaletteTests(unittest.TestCase):
    def setUp(self):
        self.studio = MapStudio.reference()
        self.studio.create("brush_test", "Village R5.4", 14, 14)

    def test_palette_uses_canonical_ids_filters_and_search(self):
        self.assertEqual(len([c for c in CATALOG if c.family == "Terrain"]), 8)
        self.assertEqual(len([c for c in CATALOG if c.family == "Décors"]), 12)
        self.assertIn("surface:stone", IDS)
        self.assertIn("feature:tree", IDS)
        self.assertEqual([c.token for c in find_cards("paVe", "Terrain")], ["cobble"])
        self.assertEqual([c.token for c in find_cards("déCORS")], [])
        self.assertEqual(MIME_BRUSH, "application/x-drawtemp-map-brush")
        for bad in ("paint:wood", "surface:lava", "feature:unknown", "../evil", "", None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                require_brush(bad)

    def test_preview_only_then_atomic_smart_stroke_and_history(self):
        baseline = self.studio.snapshot()
        preview = self.studio.smart_preview([(3, 3), (7, 3)], "surface:stone", radius=1)
        self.assertIsNotNone(preview)
        self.assertEqual(self.studio.snapshot(), baseline)
        self.assertEqual(preview.source_revision, baseline["revision"])
        self.assertIn((4, 3), preview.cells)
        self.assertIn((4, 2), preview.cells)
        self.assertTrue(all(0 <= x < 14 and 0 <= y < 14 for x, y in preview.cells))
        self.assertGreater(len(preview.neighbours), len(preview.cells))
        self.studio.smart_commit(preview)
        self.assertTrue(self.studio.snapshot()["dirty"])
        self.assertEqual(self.studio.sample((5, 3)), "stone")
        self.assertEqual(self.studio.snapshot()["revision"], baseline["revision"]+1)
        self.studio.undo()
        self.assertEqual(self.studio.snapshot()["content"], baseline["content"])
        self.studio.redo()
        self.assertEqual(self.studio.sample((5, 3)), "stone")

    def test_preview_expires_across_edit_undo_and_mission_switch(self):
        preview = self.studio.smart_preview([(5, 5)], "surface:sand")
        self.studio.paint([(7, 7)], "surface:stone")
        self.studio.undo()
        before = self.studio.snapshot()
        with self.assertRaises(AuthoringError) as error:
            self.studio.smart_commit(preview)
        self.assertEqual(error.exception.code, "stale_revision")
        self.assertEqual(before, self.studio.snapshot())
        fresh = self.studio.smart_preview([(5, 5)], "surface:sand")
        self.studio.select_map(self.studio.map_ids()[0])
        with self.assertRaises(AuthoringError):
            self.studio.smart_commit(fresh)

    def test_smart_brush_clips_edges_and_preserves_authored_work(self):
        self.studio.paint([(4, 4)], "surface:water")
        self.studio.paint([(7, 7)], "feature:tree")
        self.studio.structure("Maison", (8, 3))
        before = deepcopy(self.studio.mission())
        self.studio.smart([(0, 0), (8, 7)], "surface:stone", radius=3, shape="square")
        after = self.studio.mission()
        old_tiles = {tuple(row["pos"]): row for row in before["board"]["tiles"]}
        new_tiles = {tuple(row["pos"]): row for row in after["board"]["tiles"]}
        for pos in ((4, 4), (7, 7)):
            self.assertEqual(old_tiles[pos], new_tiles[pos])
        self.assertEqual(before["structures"], after["structures"])
        self.assertEqual(before["units"], after["units"])
        self.assertTrue(all(0 <= t["pos"][0] < 14 and 0 <= t["pos"][1] < 14
                            for t in after["board"]["tiles"]))

    def test_locked_layer_rejects_preview_before_history(self):
        self.studio.layers.set_locked(self.studio.mission_id, "Terrain", True)
        before = self.studio.snapshot()
        with self.assertRaises(AuthoringError):
            self.studio.smart_preview([(5, 5)], "surface:stone")
        self.assertEqual(before, self.studio.snapshot())

    def test_smart_feature_is_canonical_and_preserves_existing_feature(self):
        self.studio.paint([(5, 5)], "feature:tree")
        self.studio.smart([(5, 5), (6, 5)], "feature:bush", radius=0)
        features = {tuple(tile["pos"]): tile["feature"] for tile in
                    self.studio.mission()["board"]["tiles"] if "feature" in tile}
        self.assertEqual(features[(5, 5)], "tree")
        self.assertEqual(features[(6, 5)], "bush")

    def test_water_shoreline_and_bridge_axis_are_presentation_only(self):
        self.studio.paint([(6, 6)], "surface:water")
        self.studio.paint([(6, 7)], "surface:bridge")
        content = Content.from_dict(self.studio.snapshot()["content"])
        scene = scene_from_mission(content.missions[self.studio.mission_id])
        center = next(tile for tile in scene["tiles"]
                      if (tile["x"], tile["y"]) == (6, 6))
        bridge = next(tile for tile in scene["tiles"]
                      if (tile["x"], tile["y"]) == (6, 7))
        self.assertTrue(any(row["incoming"] == "shoreline"
                            for row in center["blends"]))
        self.assertIn(bridge["bridgeAxis"], ("x", "y"))
        self.assertNotIn("blends", str(content.to_dict()))
        self.assertNotIn("bridgeAxis", str(content.to_dict()))

    def test_shared_renderer_uses_identical_autoblend_after_undo_and_reload(self):
        self.studio.smart([(6, 6)], "surface:stone", radius=0)
        snapshot = self.studio.snapshot()
        content = Content.from_dict(snapshot["content"])
        scene = scene_from_mission(content.missions[self.studio.mission_id])
        cell = next(tile for tile in scene["tiles"] if (tile["x"], tile["y"]) == (6, 5))
        self.assertTrue(any(edge["incoming"] == "stone" for edge in cell["blends"]))
        self.assertTrue(all(len(edge["points"]) == 9 for edge in cell["blends"]))
        self.assertEqual(scene, scene_from_mission(content.missions[self.studio.mission_id]))
        self.assertNotIn("blends", str(content.to_dict()))
        visible = render_items(scene, Camera())
        self.assertTrue(any(row["kind"] == "tile" and row["blends"] for row in visible))
        self.studio.paint([(6, 6)], "height+")
        scene2 = scene_from_mission(Content.from_dict(
            self.studio.snapshot()["content"]).missions[self.studio.mission_id])
        cell2 = next(tile for tile in scene2["tiles"]
                     if (tile["x"], tile["y"]) == (6, 5))
        self.assertFalse(any(edge["incoming"] == "stone" for edge in cell2["blends"]))


if __name__ == "__main__":
    unittest.main()
