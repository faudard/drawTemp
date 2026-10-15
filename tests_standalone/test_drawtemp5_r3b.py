"""DrawTemp 5 R3.B: chunk reuse, relief side faces, overlays, Qt parity."""
from copy import deepcopy
import importlib.util
import os
import unittest

from drawtemp.render import (Camera, IsoProjection, TileChunkIndex, fingerprint,
                             render_items, scene_from_mission)
from drawtemp.sdk.reference import MISSION, reference_project


def large_scene(size=128):
    return {
        "mission": "large", "width": size, "height": size, "revision": 0,
        "tiles": [
            {"x": x, "y": y, "height": 0, "surface": "grass",
             "feature": "", "blocked": False, "cover": 0,
             "hazard": 0, "goal": False}
            for y in range(size) for x in range(size)
        ],
        "actors": [], "objects": [],
    }


def tile_row(rows, cell):
    key = f"tile:{cell[0]}:{cell[1]}"
    return next(t for t in rows if t["id"] == key)


class ChunkAndLayerTests(unittest.TestCase):
    def test_large_board_reuses_spatial_chunks_for_pan_and_zoom(self):
        scene = large_scene()
        index = TileChunkIndex(scene)
        self.assertEqual(len(index.chunks), 64)
        p = IsoProjection()
        c = Camera(width=320, height=240)
        c.center(*p.project(32, 32))
        rows = render_items(scene, c, tile_index=index)
        self.assertGreater(len(rows), 0)
        self.assertLess(len(rows), len(scene["tiles"]) // 10)
        self.assertEqual(rows, render_items(scene, c))  # indexed vs uncached
        for dx, dy, factor in ((32, -64, 1.2), (-115, 40, 0.6), (0, 0, 2.4)):
            c.pan_x += dx
            c.pan_y += dy
            c.zoom_at(factor, 140, 90)
            rows = render_items(scene, c, tile_index=index)
            self.assertEqual(rows, render_items(scene, c))
            self.assertLess(len(rows), len(scene["tiles"]) // 10)

    def test_mutation_replaces_only_changed_tile_and_preserves_source(self):
        scene = large_scene(32)
        index = TileChunkIndex(scene, chunk_size=8)
        before = deepcopy(index.tiles[(5, 7)])
        changed = deepcopy(scene)
        changed["revision"] += 1
        target = next(t for t in changed["tiles"] if (t["x"], t["y"]) == (5, 7))
        target["height"] = 3
        target["surface"] = "stone"
        changed_cells = index.update(changed)
        self.assertEqual(changed_cells, {(5, 7)})
        self.assertEqual(index.tiles[(5, 7)]["height"], 3)
        self.assertEqual(index.max_height, 3)
        self.assertEqual(scene["tiles"][5 + 7 * 32], before)
        self.assertEqual(index.update(changed), set())
        self.assertEqual(index.chunks[(0, 0)][(5, 7)]["surface"], "stone")

    def test_dimensions_validation_duplicates_and_negative_heights(self):
        scene = large_scene(8)
        index = TileChunkIndex(scene)
        with self.assertRaises(ValueError):
            index.update(large_scene(16))
        with self.assertRaises(ValueError):
            TileChunkIndex(scene, chunk_size=0)
        duplicate = deepcopy(scene)
        duplicate["tiles"].append(dict(duplicate["tiles"][0]))
        with self.assertRaises(ValueError):
            TileChunkIndex(duplicate)
        lower = deepcopy(scene)
        lower["tiles"][0]["height"] = -2
        self.assertEqual(TileChunkIndex(lower).min_height, -2)

    def test_adjacent_heights_expose_only_relevant_vertical_faces(self):
        scene = large_scene(8)
        for row in scene["tiles"]:
            if (row["x"], row["y"]) == (3, 3):
                row["height"] = 3
            if (row["x"], row["y"]) == (4, 3):
                row["height"] = 1
            if (row["x"], row["y"]) == (3, 4):
                row["height"] = 2
        camera = Camera(width=1024, height=768)
        camera.center(*IsoProjection().project(3, 3, 3))
        items = render_items(scene, camera)
        raised = tile_row(items, (3, 3))
        self.assertEqual((raised["eastDrop"], raised["southDrop"]), (2, 1))
        self.assertEqual(tile_row(items, (4, 3))["eastDrop"], 1)
        self.assertEqual(tile_row(items, (3, 4))["southDrop"], 2)
        self.assertEqual(tile_row(items, (2, 3))["eastDrop"], 0)
        self.assertEqual(tile_row(items, (3, 2))["southDrop"], 0)
        self.assertEqual(tile_row(items, (7, 7))["eastDrop"], 0)

    def test_overlay_compositing_is_transient_and_has_priority(self):
        scene = large_scene(8)
        baseline = fingerprint(scene)
        camera = Camera()
        camera.center(*IsoProjection().project(3, 3))
        overlays = {"reachable": [(3, 3), (4, 3)], "danger": [(3, 3)]}
        rows = render_items(scene, camera, overlays=overlays)
        self.assertEqual(tile_row(rows, (3, 3))["overlay"], "danger")
        self.assertEqual(tile_row(rows, (4, 3))["overlay"], "reachable")
        self.assertTrue(tile_row(rows, (3, 3))["overlayColor"].startswith("#"))
        self.assertEqual(fingerprint(scene), baseline)
        self.assertEqual(tile_row(render_items(scene, camera), (3, 3))["overlay"], "")
        with self.assertRaises(ValueError):
            render_items(scene, camera, overlays={"not_an_overlay": [(1, 1)]})
        with self.assertRaises(ValueError):
            render_items(scene, camera, overlays={"danger": [[1]]})

    def test_parity_reference_scene_headless_and_unchanged(self):
        content, _ = reference_project()
        mission = content.missions[MISSION]
        before = fingerprint(scene_from_mission(mission))
        editor = scene_from_mission(mission)
        player = scene_from_mission(mission)
        index = TileChunkIndex(editor)
        camera = Camera(width=900, height=650)
        a = render_items(editor, camera, tile_index=index)
        b = render_items(player, camera, tile_index=TileChunkIndex(player))
        self.assertEqual(a, b)
        self.assertEqual(fingerprint(scene_from_mission(mission)), before)


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "PySide6 optional in headless CI")
class QtRendererR3BSmoke(unittest.TestCase):
    def test_qml_shared_view_and_runtime_overlay_replacement(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtGui import QGuiApplication
        from drawtemp.render.qt_viewport import create_view
        content, _ = reference_project()
        scene = scene_from_mission(content.missions[MISSION])
        app = QGuiApplication.instance() or QGuiApplication([])
        view, controller = create_view(scene)
        try:
            self.assertIsNotNone(view.rootObject())
            original = controller._index
            controller.setOverlays({"reachable": [[2, 2]], "danger": [[3, 3]]})
            self.assertEqual(controller.overlays["danger"], ((3, 3),))
            self.assertTrue(any(item.get("overlay") == "danger" for item in controller.items))
            with self.assertRaises(ValueError):
                controller.setOverlays({"danger": [[-1, 2]]})
            self.assertEqual(controller.overlays["danger"], ((3, 3),))
            updated = deepcopy(scene)
            updated["revision"] = 2
            updated["tiles"][0]["height"] += 1
            controller.replace_scene(updated)
            self.assertIs(controller._index, original)
            self.assertEqual(controller._index.elevations[(0, 0)], updated["tiles"][0]["height"])
            self.assertEqual(controller.overlays, {})
            controller.clearOverlays()
        finally:
            view.hide()
            view.close()


if __name__ == "__main__":
    unittest.main()
