"""R52.C1 bounded visibility cache regression and CPU profiling contracts."""
from copy import deepcopy
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest

from drawtemp.render.iso_scene import (
    Camera, IsoProjection, TopDownProjection, SideProjection,
    fingerprint, render_items, pick,
)
from drawtemp.render.tile_chunks import (BoundedVisibilityCache, TileChunkIndex,
                                         DEFAULT_VISIBILITY_CACHE_BYTES)
from scripts.benchmark_r52_c1 import benchmark, percentile, scene_for_benchmark

ROOT = Path(__file__).resolve().parents[1]


class VisibilityCacheTests(unittest.TestCase):
    def test_small_view_reuses_identical_bounds_and_data(self):
        scene = scene_for_benchmark(64)
        snapshot = fingerprint(scene)
        index = TileChunkIndex(scene)
        camera = Camera(width=480, height=320)
        camera.center(*IsoProjection().project(22, 22))
        first = index.visible_tiles(camera, IsoProjection())
        second = index.visible_tiles(camera, IsoProjection())
        self.assertIsNot(first, second)
        self.assertEqual(first, second)
        stats = index.visibility_stats
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["entries"], 1)
        self.assertLessEqual(stats["bytes"], stats["budget"])
        self.assertEqual(fingerprint(scene), snapshot)

    def test_warm_vs_disabled_cache_is_identical_across_three_modes(self):
        scene = scene_for_benchmark(64)
        source = deepcopy(scene)
        cache = TileChunkIndex(scene)
        baseline = TileChunkIndex(scene, visibility_budget=1)
        projections = (IsoProjection(), TopDownProjection(), SideProjection())
        for projection in projections:
            camera = Camera(width=420, height=280)
            for center in ((10, 10), (32, 32), (48, 15), (10, 10)):
                camera.center(*projection.project(*center))
                for zoom in (.7, 1.1, 2.0):
                    camera.zoom = zoom
                    camera.center(*projection.project(*center))
                    a = render_items(scene, camera, projection, tile_index=cache)
                    b = render_items(scene, camera, projection, tile_index=baseline)
                    self.assertEqual(a, b)
                    for x, y in ((3, 3), (5, 17), (40, 43)):
                        sx, sy = camera.screen(*projection.project(x, y))
                        self.assertEqual(pick(scene, camera, sx, sy, projection),
                                         pick(source, camera, sx, sy, projection))
        self.assertEqual(scene, source)
        self.assertGreater(cache.visibility_stats["hits"], 0)
        self.assertEqual(baseline.visibility_stats["hits"], 0)

    def test_dirty_rebuild_invalidates_before_access(self):
        scene = scene_for_benchmark(32)
        index = TileChunkIndex(scene)
        camera = Camera()
        camera.center(*IsoProjection().project(10, 10))
        original = index.visible_tiles(camera)
        self.assertTrue(original)
        self.assertEqual(index.visibility_stats["entries"], 1)
        changed = deepcopy(scene)
        tile = next(t for t in changed["tiles"] if (t["x"], t["y"]) == (10, 10))
        tile["height"] = 7
        tile["surface"] = "water"
        self.assertEqual(index.update(changed), {(10, 10)})
        self.assertEqual(index.visibility_stats["entries"], 0)
        self.assertEqual(index.visibility_stats["bytes"], 0)
        refreshed = index.visible_tiles(camera)
        self.assertTrue(any(t["x"] == 10 and t["y"] == 10 and t["height"] == 7
                            for t in refreshed))
        # Same content must not invalidate hot visible bounds.
        index.visible_tiles(camera)
        self.assertEqual(index.update(changed), set())
        self.assertEqual(index.visibility_stats["entries"], 1)
        self.assertEqual(scene["tiles"][10 + 10 * 32]["height"], 0)

    def test_stress_cache_never_exceeds_size_or_entry_limit(self):
        cache = BoundedVisibilityCache(budget=4096, max_entries=3)
        for n in range(20):
            coords = ((x, n) for x in range(4))
            cache.put((n, n + 1, n, n + 1), tuple(coords))
            self.assertLessEqual(cache.stats()["entries"], 3)
            self.assertLessEqual(cache.stats()["bytes"], 4096)
        self.assertGreater(cache.stats()["evictions"], 0)
        self.assertEqual(cache.get((19, 20, 19, 20)), tuple((x, 19) for x in range(4)))
        before = cache.stats()["entries"]
        self.assertFalse(cache.put(("huge",), tuple((x, 0) for x in range(999))))
        self.assertEqual(cache.stats()["entries"], before)
        self.assertEqual(cache.stats()["bypasses"], 1)
        cache.clear()
        self.assertEqual(cache.stats()["bytes"], 0)
        self.assertEqual(cache.stats()["entries"], 0)

    def test_invalid_limits_rejected_without_bool_as_integer(self):
        for kwargs in ({"budget": 0}, {"budget": True}, {"budget": -1},
                       {"max_entries": 0}, {"max_entries": 65},
                       {"max_entries": True}, {"max_entries": 1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                BoundedVisibilityCache(**kwargs)
        scene = scene_for_benchmark(16)
        with self.assertRaises(ValueError):
            TileChunkIndex(scene, visibility_budget=0)
        self.assertEqual(TileChunkIndex(scene).visibility_stats["budget"],
                         DEFAULT_VISIBILITY_CACHE_BYTES)

    def test_culling_outside_world_and_oversized_views_use_safe_fallback(self):
        scene = scene_for_benchmark(64)
        index = TileChunkIndex(scene, visibility_budget=2048)
        camera = Camera(width=1200, height=900)
        camera.center(*IsoProjection().project(30, 30))
        first = index.visible_tiles(camera)
        self.assertTrue(first)
        self.assertGreater(index.visibility_stats["bypasses"], 0)
        self.assertEqual(index.visible_tiles(camera), first)
        self.assertEqual(index.visibility_stats["entries"], 0)
        camera.center(*IsoProjection().project(-10000, -10000))
        self.assertEqual(index.visible_tiles(camera), ())

    def test_quantiles_are_monotonic_and_benchmark_tracks_parity(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], 95), 5)
        self.assertLessEqual(percentile([1, 2, 3, 4, 5], 50),
                             percentile([1, 2, 3, 4, 5], 99))
        with self.assertRaises(ValueError):
            percentile([], 95)
        report = benchmark(size=16, frames=8)
        self.assertFalse(report["physical_gpu_verified"])
        self.assertTrue(report["renderer_parity"])
        self.assertEqual({x["mode"] for x in report["profiles"]},
                         {"isometric", "top_down", "side"})
        for profile in report["profiles"]:
            self.assertGreaterEqual(profile["baseline"]["cpu_ms_p95"], 0)
            self.assertLessEqual(
                profile["bounded_cache"]["cache"]["bytes"],
                profile["bounded_cache"]["cache"]["budget"],
            )


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "Qt optional for headless-only suite")
class QtVisibilityStatsTests(unittest.TestCase):
    def test_qquick_controller_exposes_same_bounded_visibility_cache(self):
        program = r"""
from PySide6.QtGui import QGuiApplication
from drawtemp.render.qt_viewport import create_view
from scripts.benchmark_r52_c1 import scene_for_benchmark
app = QGuiApplication.instance() or QGuiApplication([])
scene = scene_for_benchmark(32)
view, renderer = create_view(scene)
assert view.rootObject() is not None
renderer.resizeViewport(460, 320)
renderer.panBy(20, -12)
before = renderer.visibilityStats
renderer.refresh()
after = renderer.visibilityStats
assert after["hits"] >= before["hits"]
assert after["entries"] <= 16
assert after["bytes"] <= after["budget"]
assert after["budget"] == 256 * 1024
view.close()
"""
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   QT_QUICK_BACKEND="software")
        result = subprocess.run([sys.executable, "-c", program], cwd=ROOT,
                                env=env, text=True, capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
