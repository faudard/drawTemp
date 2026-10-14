"""3.7.32H — Tk painterly masks, cache reuse and Player/Studio parity."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor_render_cache import EditorRenderCache
from sporebound.iso_map import IsoTerrainAtlas, render_isometric
from sporebound.model import Content, Tile
from sporebound.terrain_autoblend import blend_edges
from sporebound.terrain_transition_masks import painted_mask_key


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Needs Tk under Xvfb')
class PaintedTransitionGuiTests(unittest.TestCase):
    @staticmethod
    def mission():
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'painted_masks', 'Painted masks', 14, 14)
        scene = Content.from_dict(data).missions['painted_masks']
        scene.board.tiles[(7, 7)] = Tile(surface='sand')
        scene.board.tiles[(7, 6)] = Tile(surface='stone')
        scene.board.tiles[(8, 7)] = Tile(surface='grass')
        scene.board.tiles[(6, 7)] = Tile(surface='cobble')
        return scene

    def test_png_composition_at_three_zooms_and_cached_photo_lifetime(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        canvas = tk.Canvas(root)
        source = IsoTerrainAtlas(canvas)
        scene = self.mission()
        for size in (24, 54, 96):
            with self.subTest(size=size):
                render_isometric(canvas, scene.board, scene, scene.units,
                                 cell_size=size, layers={}, atlas=source,
                                 selected_cell=(0, 0), selected_tiles=())
                tags = canvas.find_withtag('painted_transition')
                self.assertGreaterEqual(len(tags), 3)
                self.assertTrue(all(canvas.type(i) == 'image' for i in tags))
                self.assertTrue(source._watercolor)
                self.assertTrue(source._mask_sources)
                self.assertFalse(source._mask_unavailable)
                edge = blend_edges(scene.board, (7, 7))[0]
                key = painted_mask_key(edge)
                image = source.blend_tile(*key, size)
                self.assertIs(image, source.blend_tile(*key, size))
                self.assertEqual((image.width(), image.height()),
                                 (size*2, size))
        self.assertLessEqual(len(source._mask_sources), 96)
        self.assertLessEqual(len(source._mask_tiles), 288)

    def test_editor_retained_and_full_player_like_frame_identical(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        left, right = tk.Canvas(root), tk.Canvas(root)
        scene = self.mission()
        a, b = IsoTerrainAtlas(left), IsoTerrainAtlas(right)
        options = dict(cell_size=54, layers={},
                       selected_cell=(0, 0), selected_tiles=())
        retained = EditorRenderCache(left)
        retained.draw(scene.board, scene, scene.units, atlas=a, **options)
        render_isometric(right, scene.board, scene, scene.units, atlas=b, **options)
        def visible(canvas):
            return [(canvas.type(i), tuple(canvas.coords(i)),
                     canvas.itemcget(i, 'tags'),
                     canvas.itemcget(i, 'fill') if canvas.type(i) in ('polygon', 'line') else '')
                    for i in canvas.find_all()]
        self.assertEqual(visible(left), visible(right))
        self.assertTrue(left.find_withtag('painted_transition'))
        # The second draw reuses Tk images; it must not drop their refs.
        previously = dict(a._mask_tiles)
        retained.draw(scene.board, scene, scene.units, atlas=a, **options)
        self.assertEqual(previously, a._mask_tiles)

    def test_legacy_atlas_uses_vector_fallback_not_separate_art(self):
        import tkinter as tk
        from sporebound.iso_map import DEFAULT_TERRAIN_ATLAS
        root = tk.Tk()
        self.addCleanup(root.destroy)
        canvas = tk.Canvas(root)
        scene = self.mission()
        atlas = IsoTerrainAtlas(canvas, path=DEFAULT_TERRAIN_ATLAS)
        render_isometric(canvas, scene.board, scene, scene.units,
                         cell_size=54, layers={}, atlas=atlas,
                         selected_cell=(0, 0), selected_tiles=())
        self.assertFalse(canvas.find_withtag('painted_transition'))
        self.assertTrue(canvas.find_withtag('terrain_autoblend'))


if __name__ == '__main__':
    unittest.main()
