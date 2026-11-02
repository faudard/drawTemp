"""Headless regression checks for map viewport resizing and centering."""
import unittest

from sporebound.map_viewport_controls import fit_zoom, scroll_fraction


class ViewportControlTests(unittest.TestCase):
    def test_fits_small_scene_without_exceeding_limit(self):
        self.assertEqual(fit_zoom(54, 432, 324, 800, 600), 91)

    def test_large_map_uses_minimum_supported_tile_size(self):
        self.assertEqual(fit_zoom(54, 3200, 2400, 640, 480), 24)

    def test_zero_size_scene_is_safe(self):
        self.assertEqual(fit_zoom(54, 0, 300, 800, 600), 54)

    def test_preserves_scroll_when_scene_is_larger_than_viewport(self):
        self.assertAlmostEqual(scroll_fraction(0, 1000, 400, 500, 200), 0.3)
        self.assertAlmostEqual(scroll_fraction(-100, 900, 400, 400, 200), 0.3)

    def test_scroll_fraction_clamps_and_handles_short_scene(self):
        self.assertEqual(scroll_fraction(0, 100, 400, 50, 200), 0)
        self.assertEqual(scroll_fraction(0, 1000, 400, -50, 200), 0)
        self.assertEqual(scroll_fraction(0, 1000, 400, 2000, 200), 1)


if __name__ == '__main__':
    unittest.main()
