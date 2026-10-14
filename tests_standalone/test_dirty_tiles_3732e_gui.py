"""True Tk parity: selective dirty-terrain Canvas vs full isometric painter."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.editor_render_cache import EditorRenderCache
from sporebound.iso_map import render_isometric
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk/Xvfb')
class DirtyTilesGuiTests(unittest.TestCase):
    def test_65_and_128_dirty_water_bridge_undo_redo_and_repaints(self):
        import tkinter as tk
        for size in (65, 128):
            with self.subTest(size=size):
                root = tk.Tk()
                try:
                    root.geometry('720x510')
                    canvas = tk.Canvas(root)
                    reference = tk.Canvas(root)
                    canvas.pack()
                    root.update_idletasks()
                    raw = add_blank_mission(
                        Content.load(DEFAULT_CONTENT).to_dict(),
                        'dirty_map', 'Dirty Tiles', size, size)
                    doc = Document(Content.from_dict(raw))
                    renderer = EditorRenderCache(canvas)
                    options = {
                        'cell_size': 54, 'layers': {},
                        'selected_cell': None, 'selected_tiles': (),
                    }
                    revision = 0

                    def compare(expected_path):
                        nonlocal revision
                        revision += 1
                        mission = Content.from_dict(doc.data).missions['dirty_map']
                        renderer.draw(
                            mission.board, mission, mission.units,
                            scene_revision=(revision, mission.id), **options)
                        render_isometric(reference, mission.board,
                                         mission, mission.units, **options)
                        snapshot = lambda view: [
                            (view.type(i), view.coords(i),
                             {k: v[-1] for k, v in view.itemconfigure(i).items()})
                            for i in view.find_all()
                        ]
                        self.assertEqual(snapshot(canvas), snapshot(reference))
                        self.assertEqual(canvas.cget('scrollregion'),
                                         reference.cget('scrollregion'))
                        self.assertEqual(renderer.stats.get('fast_path'),
                                         expected_path)
                        self.assertLessEqual(len(canvas.find_all()),
                                             20 * size * size)
                        return canvas.find_all()

                    compare('full')
                    doc.paint_many('dirty_map', [(10, 10)], 'surface:water')
                    compare('dirty_tiles')
                    self.assertEqual(renderer.stats['dirty_cells'], 9)
                    self.assertEqual(renderer.stats['affected_cells'], 9)
                    doc.paint_many('dirty_map', [(10, 11)], 'surface:bridge')
                    compare('dirty_tiles')
                    doc.undo()
                    compare('dirty_tiles')
                    doc.redo()
                    compare('dirty_tiles')
                    doc.paint_many('dirty_map', [(10, 10)], 'height+')
                    compare('full')
                    options['cell_size'] = 96
                    compare('full')
                    options['cell_size'] = 24
                    compare('full')
                    doc.paint_many('dirty_map', [(x, 13) for x in range(32)],
                                   'surface:water')
                    compare('full')
                finally:
                    root.destroy()

    def test_selected_cell_overlay_and_conservative_structure_fallback(self):
        import tkinter as tk
        root = tk.Tk()
        try:
            root.geometry('720x510')
            canvas = tk.Canvas(root)
            canvas.pack()
            root.update_idletasks()
            raw = add_blank_mission(
                Content.load(DEFAULT_CONTENT).to_dict(),
                'dirty_map', 'Dirty Tiles', 65, 65)
            doc = Document(Content.from_dict(raw))
            renderer = EditorRenderCache(canvas)
            options = {'cell_size': 54, 'layers': {},
                       'selected_cell': (3, 3), 'selected_tiles': ()}
            revision = 0

            def draw():
                nonlocal revision
                revision += 1
                mission = Content.from_dict(doc.data).missions['dirty_map']
                renderer.draw(mission.board, mission, mission.units,
                              scene_revision=(revision, mission.id), **options)

            draw()
            doc.paint_many('dirty_map', [(3, 3)], 'surface:water')
            draw()
            self.assertEqual(renderer.stats['fast_path'], 'dirty_tiles')
            self.assertEqual(len(canvas.find_withtag('selection')), 1)
            options['selected_cell'] = (4, 4)
            doc.paint_many('dirty_map', [(4, 4)], 'surface:water')
            draw()
            self.assertEqual(renderer.stats['fast_path'], 'dirty_tiles')
            self.assertEqual(len(canvas.find_withtag('selection')), 1)
            scene = next(m for m in doc.data['missions']
                         if m['id'] == 'dirty_map')
            scene['units'] = [Content.load(DEFAULT_CONTENT).
                              missions['garden'].units[0].__dict__.copy()]
            # No actor-contract rewriting in fast path: if invalid, reject.
            # The planner contract is tested headless with a real Unit.
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
