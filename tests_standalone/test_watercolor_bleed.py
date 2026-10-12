"""Headless, dependency-free contract tests for the watercolor bleed cleaner."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location(
    "bleed_cleanup", ROOT / "scripts/cleanup_watercolor_bleed.py")
module = module_from_spec(spec)
spec.loader.exec_module(module)


class WatercolorBleedTests(unittest.TestCase):
    def test_only_disconnected_edge_components_removed(self):
        # background, main silhouette, top-row artefact, detached center
        stats = [
            [0, 0, 384, 341, 100000],
            [50, 40, 250, 280, 42000],
            [160, 0, 56, 16, 790],
            [192, 220, 15, 20, 200],
        ]
        self.assertEqual(module.border_fragments(stats, 1, (384, 341)), [2])

    def test_do_not_strip_primary_silhouette_at_border(self):
        stats = [[0, 0, 384, 341, 10000],
                 [0, 0, 380, 340, 38000],
                 [100, 50, 50, 90, 500]]
        self.assertEqual(module.border_fragments(stats, 1, (384, 341)), [])

    def test_small_disconnected_speckles_retained(self):
        stats = [[0, 0, 384, 341, 10000],
                 [55, 30, 280, 290, 40000],
                 [0, 20, 4, 12, 40]]
        self.assertEqual(module.border_fragments(stats, 1, (384, 341)), [])
        self.assertEqual(
            module.border_fragments(stats, 1, (384, 341), min_area=30), [2])

    def test_frame_cleanup_dependencies_are_optional_at_import(self):
        # Lazy PIL/numpy/cv2 import lets the normal standalone suite run
        # without introducing a dependency for the headless tactical engine.
        self.assertEqual(module.EXEMPT_GROUPS, {"vfx", "bestiary"})
        self.assertTrue(callable(module.clean_archive))


if __name__ == "__main__":
    unittest.main()
