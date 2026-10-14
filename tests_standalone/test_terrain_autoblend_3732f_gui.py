"""VF 3.7.32F — real Tk partial redraw and shared renderer parity."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.editor_render_cache import EditorRenderCache
from sporebound.iso_map import render_isometric
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires a Tk display under Xvfb')
class AutoBlendGuiTests(unittest.TestCase):
    def test_one_tile_edit_repaints_at_most_3x3_and_matches_full_render(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        left, right = tk.Canvas(root), tk.Canvas(root)
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'autoblend_gui', 'AutoBlend', 24, 24)
        doc = Document(Content.from_dict(data))
        renderer = EditorRenderCache(left, max_retained_cells=1)
        mission_id = 'autoblend_gui'
        for zoom in (24, 54, 96):
            with self.subTest(zoom=zoom):
                renderer.invalidate()
                # Flat, nearby actors use standard render paths, while the
                # edited cell remains >6 cells away from their footprints.
                before = Content.from_dict(doc.data).missions[mission_id]
                options = dict(cell_size=zoom, layers={},
                               selected_cell=(0, 0), selected_tiles=())
                renderer.draw(before.board, before, before.units,
                              scene_revision=zoom * 10, **options)
                doc.paint_many(mission_id, [(11, 11)], 'surface:dirt')
                after = Content.from_dict(doc.data).missions[mission_id]
                renderer.draw(after.board, after, after.units,
                              scene_revision=zoom * 10 + 1, **options)
                self.assertEqual(renderer.stats['fast_path'], 'dirty_tiles')
                self.assertLessEqual(renderer.stats['affected_cells'], 9)
                render_isometric(right, after.board, after, after.units,
                                 **options)
                def shape_snapshot(canvas):
                    return [(canvas.type(item), canvas.coords(item),
                             canvas.itemcget(item, 'fill') if canvas.type(item)
                             in ('polygon', 'rectangle', 'oval', 'line') else '')
                            for item in canvas.find_all()]
                self.assertEqual(shape_snapshot(left), shape_snapshot(right))
                self.assertTrue(left.find_withtag('terrain_autoblend'))
                doc.undo()

    def test_water_still_uses_shorelines_without_land_blend(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        canvas = tk.Canvas(root)
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'waterblend_gui', 'Water AutoBlend', 12, 12)
        doc = Document(Content.from_dict(data))
        doc.paint_many('waterblend_gui', [(6, 6)], 'surface:water')
        scene = Content.from_dict(doc.data).missions['waterblend_gui']
        render_isometric(canvas, scene.board, scene, scene.units,
                         cell_size=54, layers={}, selected_cell=(0, 0),
                         selected_tiles=())
        self.assertFalse(canvas.find_withtag('terrain_autoblend'))
        # A neighbouring sand cell transitions into grass without altering
        # the water, bridge axis or battle-blocking rules.
        doc.paint_many('waterblend_gui', [(6, 7)], 'surface:sand')
        scene = Content.from_dict(doc.data).missions['waterblend_gui']
        render_isometric(canvas, scene.board, scene, scene.units,
                         cell_size=54, layers={}, selected_cell=(0, 0),
                         selected_tiles=())
        self.assertTrue(canvas.find_withtag('terrain_autoblend'))
        self.assertTrue(scene.board.tile((6, 6)).blocked)


if __name__ == '__main__':
    unittest.main()
