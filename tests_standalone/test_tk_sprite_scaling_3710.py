"""Regression tests: Tk sprite resize must sample the whole PNG."""
import os
import unittest

from sporebound.tk_renderer import CanvasRenderer


class SpriteScalingMathTests(unittest.TestCase):
    def test_common_jeanne_frames_resize_at_actual_tactical_cell_size(self):
        self.assertEqual(CanvasRenderer._nearest_scale_factors(384, 52), (2, 15))
        self.assertEqual(CanvasRenderer._nearest_scale_factors(341, 52), (3, 20))
        self.assertEqual(CanvasRenderer._nearest_scale_factors(64, 52), (4, 5))

    def test_factors_have_bounded_error_at_zoom_levels(self):
        for source in (64, 96, 128, 192, 341, 384, 512):
            for target in (40, 52, 64, 78, 104):
                zoom, skip = CanvasRenderer._nearest_scale_factors(source, target)
                result = (source * zoom + skip - 1) // skip
                with self.subTest(source=source, target=target):
                    self.assertGreaterEqual(zoom, 1)
                    self.assertGreaterEqual(skip, 1)
                    self.assertLessEqual(abs(result - target), 6)

    def test_invalid_dimensions_are_rejected(self):
        for source, target in ((0, 52), (-1, 52), (64, 0), (64, -1)):
            with self.assertRaises(ValueError):
                CanvasRenderer._nearest_scale_factors(source, target)


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Live Tk/Xvfb needed to check source coverage")
class TkSpriteScalingRegressionTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.canvas = tk.Canvas(self.root, width=320, height=240)
        self.canvas.pack()
        self.root.update()
        self.renderer = CanvasRenderer(self.canvas)

    def tearDown(self):
        self.renderer.dispose()
        self.root.destroy()

    def test_high_resolution_sprite_keeps_lower_right_pixels(self):
        import tkinter as tk
        source = tk.PhotoImage(master=self.canvas, width=384, height=341)
        source.put("#ff00aa", to=(300, 200, 355, 310))
        # Regression: the old single-copy zoom/subsample completely omitted
        # all pixels outside the source's upper-left handful of columns.
        scaled = self.renderer._cell_photo(source, 52)
        self.assertEqual((scaled.width(), scaled.height()), (52, 52))
        self.assertEqual(scaled.get(45, 40), (255, 0, 170))
        self.assertTrue(scaled.transparency_get(2, 2))
        self.assertIs(scaled, self.renderer._cell_photo(source, 52))

    def test_existing_64px_atlas_preserves_bottom_right(self):
        import tkinter as tk
        source = tk.PhotoImage(master=self.canvas, width=64, height=64)
        source.put("#25d8c0", to=(42, 42, 61, 61))
        scaled = self.renderer._cell_photo(source, 52)
        self.assertEqual(scaled.get(40, 40), (37, 216, 192))

    def test_cache_is_zoom_specific(self):
        import tkinter as tk
        source = tk.PhotoImage(master=self.canvas, width=384, height=341)
        source.put("#ff00aa", to=(300, 200, 355, 310))
        small = self.renderer._cell_photo(source, 52)
        large = self.renderer._cell_photo(source, 78)
        self.assertIsNot(small, large)
        self.assertEqual((large.width(), large.height()), (78, 78))
        self.assertIs(large, self.renderer._cell_photo(source, 78))


if __name__ == "__main__":
    unittest.main()
