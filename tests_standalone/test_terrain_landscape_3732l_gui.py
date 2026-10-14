"""3.7.32L GUI — natural maps share the same isometric renderer."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_map import render_isometric
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires a Tk display')
class NaturalMapGuiTests(unittest.TestCase):
    def test_all_zoom_levels_have_stable_shared_topography(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        first, second = tk.Canvas(root), tk.Canvas(root)
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'landscape_gui', 'Landscape render', 32, 32)
        doc = Document(Content.from_dict(data))
        plan = doc.preview_natural_map(
            'landscape_gui', (3, 3), (26, 26), seed=42,
            style='bocage', vegetation=2)
        doc.confirm_natural_map(plan)
        mission = Content.from_dict(doc.data).missions['landscape_gui']
        for zoom in (24, 54, 96):
            with self.subTest(zoom=zoom):
                params = dict(cell_size=zoom, layers={},
                              selected_cell=(0, 0), selected_tiles=())
                render_isometric(first, mission.board, mission, mission.units,
                                 **params)
                render_isometric(second, mission.board, mission, mission.units,
                                 **params)
                def snapshot(canvas):
                    return tuple((canvas.type(item),
                                  tuple(canvas.coords(item)),
                                  canvas.itemcget(item, 'fill')
                                  if canvas.type(item) in
                                  ('line', 'rectangle', 'oval', 'polygon') else '')
                                 for item in canvas.find_all())
                self.assertEqual(snapshot(first), snapshot(second))
                self.assertTrue(first.find_all())
                self.assertTrue(all(mission.board.tile(point).surface in
                                    ('dirt', 'bridge') for point in plan.road))


if __name__ == '__main__':
    unittest.main()
