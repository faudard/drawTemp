"""Real Tk 3.7.20A roof visibility and isometric picking, opt-in via Xvfb."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_map import render_isometric
from sporebound.iso_structures import place_structure
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Needs Tk/Xvfb')
class InteriorCutawayGUI(unittest.TestCase):
    def test_manual_and_automatic_cutaway_at_three_zooms(self):
        import tkinter as tk

        base = Content.load(DEFAULT_CONTENT)
        content = add_blank_mission(base.to_dict(), 'interior_gui',
                                    'Maison', 16, 16)
        content = place_structure(content, 'interior_gui', 'Maison', (3, 3))
        mission = Content.from_dict(content).missions['interior_gui']
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root, width=950, height=740)
            canvas.pack()
            root.update()
            atlas = IsoBuildingAtlas(canvas)

            def draw(size, *, interiors=False, selection=(0, 0)):
                return render_isometric(
                    canvas, mission.board, mission, mission.units,
                    cell_size=size,
                    layers={'Terrain': True, 'Relief': True, 'Décors': True,
                            'Bâtiments': True, 'Toitures': True,
                            'Intérieurs': interiors},
                    selected_cell=selection, selected_tiles=(),
                    building_atlas=atlas)

            for size in (24, 54, 96):
                with self.subTest(zoom=size):
                    outer = draw(size)
                    self.assertEqual(len(canvas.find_withtag('architecture_sprite')), 1)
                    self.assertEqual(outer.hit_test(*outer.center((4, 4))), (4, 4))

                    cut = draw(size, interiors=True)
                    self.assertEqual(len(canvas.find_withtag('architecture_sprite')), 0)
                    self.assertGreater(len(canvas.find_withtag('architecture_interior')), 0)
                    self.assertEqual(cut.hit_test(*cut.center((4, 4))), (4, 4))

                    automatic = draw(size, selection=(4, 4))
                    self.assertEqual(len(canvas.find_withtag('architecture_sprite')), 0)
                    self.assertGreater(len(canvas.find_withtag('architecture_interior')), 0)
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
