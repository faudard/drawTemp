"""R3.D bounded chunk GPU texture path: parity, invalidation, Qt smokes."""
from copy import deepcopy
import importlib.util
import os
import unittest

from drawtemp.render import Camera, IsoProjection, TileChunkIndex, render_items
from drawtemp.render.texture_batches import (
    BoundedImageStore, TerrainTextureBatches, chunk_key, is_static_tile,
)
from tests_standalone.test_drawtemp5_r3b import large_scene


class FakeImage:
    def __init__(self, width, height):
        self.w, self.h = width, height

    def width(self):
        return self.w

    def height(self):
        return self.h


class R3DContracts(unittest.TestCase):
    def test_lru_evicts_and_limits_bytes(self):
        store = BoundedImageStore(1000)
        self.assertTrue(store.put("a", FakeImage(10, 10)))
        self.assertTrue(store.put("b", FakeImage(10, 10)))
        self.assertIsNotNone(store.get("a"))
        self.assertTrue(store.put("c", FakeImage(10, 10)))
        self.assertIsNone(store.get("b"))
        self.assertIsNotNone(store.get("a"))
        self.assertLessEqual(store.used_bytes, 1000)
        self.assertFalse(store.put("huge", FakeImage(100, 100)))
        self.assertLessEqual(store.used_bytes, 1000)
        store.clear()
        self.assertEqual(store.used_bytes, 0)
        with self.assertRaises(ValueError):
            BoundedImageStore(0)

    def test_only_simple_flat_terrain_can_be_textured(self):
        scene = large_scene(12)
        camera = Camera(width=800, height=640)
        camera.center(*IsoProjection().project(6, 6))
        rows = render_items(scene, camera)
        tile = next(row for row in rows if row["kind"] == "tile")
        self.assertTrue(is_static_tile(tile))
        for key, value in (("height", 1), ("eastDrop", 1), ("feature", "tree"),
                           ("goal", True), ("blocked", True), ("cover", 1),
                           ("hazard", 1)):
            changed = dict(tile, **{key: value})
            self.assertFalse(is_static_tile(changed), key)
        self.assertFalse(is_static_tile({"kind": "actor"}))
        self.assertEqual(chunk_key(7, 8), (0, 1))

    def test_single_edit_invalidates_neighboring_chunks_only(self):
        scene = large_scene(48)
        index = TileChunkIndex(scene)
        texture = TerrainTextureBatches(index)
        assert texture.invalidate({(8, 8)}) == {(1, 1), (0, 1), (1, 0)}
        self.assertEqual(texture.generations[(1, 1)], 1)
        self.assertEqual(len(texture.generations), 3)
        old = index
        changed = deepcopy(scene)
        changed["tiles"][8 + 8*48]["height"] = 1
        dirty = old.update(changed)
        self.assertEqual(dirty, {(8, 8)})
        texture.invalidate(dirty)
        self.assertEqual(texture.generations[(1, 1)], 2)
        texture.reset(TileChunkIndex(large_scene(8)))
        self.assertEqual(texture.generations, {})
        self.assertEqual(texture.store.used_bytes, 0)

    def test_too_small_budget_falls_back_without_painting(self):
        scene = large_scene(32)
        index = TileChunkIndex(scene)
        camera = Camera(width=600, height=400)
        camera.center(*IsoProjection().project(8, 8))
        texture = TerrainTextureBatches(index, budget=64)
        tiles = render_items(scene, camera, tile_index=index)
        images, replaced = texture.prepare(tiles)
        self.assertEqual(images, [])
        self.assertEqual(replaced, set())
        self.assertEqual(texture.store.used_bytes, 0)


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "PySide6 needed for Qt Quick texture test")
class R3DQtSmoke(unittest.TestCase):
    def test_shared_viewport_batching_and_fallback(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtGui import QGuiApplication
        from drawtemp.render.qt_viewport import create_view

        app = QGuiApplication.instance() or QGuiApplication([])
        scene = large_scene(48)
        view, renderer = create_view(scene)
        try:
            self.assertIsNotNone(view.rootObject())
            self.assertTrue(renderer.textureBatching)
            self.assertGreater(renderer.textureStats["tiles"], 0)
            self.assertLess(len(renderer.displayItems), len(renderer.items))
            self.assertLessEqual(renderer.textureStats["bytes"],
                                 renderer.textureStats["budget"])
            self.assertTrue(renderer.tileBatches)
            url = renderer.tileBatches[0]["url"]
            self.assertTrue(url.startswith("image://drawtemp-tiles/"))
            batch_cell = next(item for item in renderer.items
                              if item["kind"] == "tile" and
                              renderer.isBatchedCell(item["x"], item["y"]))
            self.assertNotIn(batch_cell, renderer.displayItems)
            # Selected terrain gets a complete original delegate again.
            renderer.selectCell(batch_cell["x"], batch_cell["y"])
            self.assertIn(batch_cell["id"], [item["id"] for item
                                               in renderer.displayItems])
            old_misses = renderer.textureStats["misses"]
            renderer.panBy(12, -15)
            self.assertGreaterEqual(renderer.textureStats["hits"], 1)
            self.assertGreaterEqual(renderer.textureStats["misses"], old_misses)
            original_index = renderer._index
            changed = deepcopy(scene)
            changed["tiles"][8 + 8*48]["surface"] = "stone"
            renderer.replace_scene(changed)
            self.assertIs(renderer._index, original_index)
            self.assertTrue(renderer.tileBatches)
            self.assertLessEqual(renderer.textureStats["bytes"],
                                 renderer.textureStats["budget"])
            view.rootObject().setProperty("showGrid", False)
            self.assertFalse(view.rootObject().property("showGrid"))
            # Cache image lookup should return a real QImage.
            row = renderer.tileBatches[0]
            ident = row["url"].split("image://drawtemp-tiles/", 1)[1]
            from PySide6.QtCore import QSize
            img = renderer._image_provider.requestImage(ident, QSize(), QSize())
            self.assertFalse(img.isNull())
        finally:
            view.hide()
            view.close()


if __name__ == "__main__":
    unittest.main()
