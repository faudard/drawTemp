"""3.7.32G — smoke the actual Tk watercolor source at Editor/Player zooms."""
import os
import unittest

from sporebound.iso_map import (
    ATLAS_MATERIALS, DEFAULT_TERRAIN_ATLAS, IsoTerrainAtlas, render_isometric,
)
from sporebound.model import Board, Tile
from sporebound.terrain_watercolor import MATERIALS, PIGMENTS


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires a real Xvfb/Tk display')
class WatercolorAtlasGuiTests(unittest.TestCase):
    def test_default_atlas_is_real_rgba_tk_image_at_24_54_96(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        canvas = tk.Canvas(root)
        self.assertEqual(tuple(ATLAS_MATERIALS), MATERIALS)
        watercolor = IsoTerrainAtlas(canvas)
        self.assertTrue(watercolor._watercolor)
        for zoom in (24, 54, 96):
            for name in MATERIALS:
                for variant in (0, 1):
                    with self.subTest(zoom=zoom, name=name, variant=variant):
                        tile = watercolor.tile(name, zoom, variant)
                        self.assertIsNotNone(tile)
                        self.assertEqual((tile.width(), tile.height()),
                                         (zoom*2, zoom))
                        self.assertIs(tile, watercolor.tile(name, zoom, variant))
        self.assertIsNotNone(watercolor._source)
        self.assertEqual(watercolor._source.width(), 1536)
        self.assertEqual(watercolor._source.height(), 48)
        self.assertTrue(watercolor._watercolor)

    def test_explicit_png_override_preserves_legacy_atlas(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        canvas = tk.Canvas(root)
        legacy = IsoTerrainAtlas(canvas, path=DEFAULT_TERRAIN_ATLAS)
        self.assertFalse(legacy._watercolor)
        self.assertIsNotNone(legacy.tile('grass', 54))
        self.assertEqual(legacy._source.width(), 1536)

    def test_full_renderer_emits_watercolor_images_and_autoblend(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        canvas = tk.Canvas(root)
        board = Board(4, 4)
        board.tiles[(2, 2)] = Tile(surface='dirt')
        board.tiles[(2, 1)] = Tile(surface='stone')
        # Use an authored mission's shape through a tiny local mission fixture.
        from sporebound.__main__ import DEFAULT_CONTENT
        from sporebound.authoring import add_blank_mission
        from sporebound.model import Content
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'watercolor_gui', 'Watercolor', 8, 8)
        mission = Content.from_dict(data).missions['watercolor_gui']
        mission.board.tiles[(3, 3)] = Tile(surface='dirt')
        mission.board.tiles[(3, 2)] = Tile(surface='stone')
        terrain = IsoTerrainAtlas(canvas)
        render_isometric(canvas, mission.board, mission, mission.units,
                         cell_size=54, layers={}, atlas=terrain,
                         selected_cell=(0, 0), selected_tiles=())
        self.assertTrue(terrain._watercolor)
        self.assertTrue(canvas.find_withtag('terrain_autoblend'))
        self.assertTrue(any(canvas.type(item) == 'image'
                            for item in canvas.find_all()))


if __name__ == '__main__':
    unittest.main()
