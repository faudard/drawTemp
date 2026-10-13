"""3.7.17B: real Tk proof that repaint does not lose the authored building PNG."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_map import render_isometric
from sporebound.iso_structures import place_structure, remove_structure
from sporebound.model import Content


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Needs a real Tk/Xvfb display")
class PersistentArchitectureGUI(unittest.TestCase):
    def test_persistent_house_survives_repaint_and_is_removed_explicitly(self):
        import tkinter as tk
        base = Content.load(DEFAULT_CONTENT)
        data = add_blank_mission(base.to_dict(), "visual_house", "Atelier", 16, 16)
        doc = Document(Content.from_dict(data))
        doc.replace(place_structure(doc.data, "visual_house",
                                    "Maison", (3, 3), 1, door_slot=1))
        root = tk.Tk()
        try:
            root.geometry("900x700")
            canvas = tk.Canvas(root, width=900, height=700)
            canvas.pack()
            root.update()
            atlas = IsoBuildingAtlas(canvas)
            def draw():
                mission = Content.from_dict(doc.data).missions["visual_house"]
                return render_isometric(
                    canvas, mission.board, mission, mission.units,
                    cell_size=54, layers={"Terrain": True, "Relief": True,
                                          "Bâtiments": True, "Toitures": True},
                    selected_cell=(0, 0), selected_tiles=(),
                    building_atlas=atlas)
            geo = draw()
            self.assertEqual(len(canvas.find_withtag("architecture_sprite")), 1)
            self.assertEqual(geo.hit_test(*geo.center((4, 4))), (4, 4))
            doc.paint_many("visual_house", [(3, 3)], "feature-erase")
            draw()
            self.assertEqual(len(canvas.find_withtag("architecture_sprite")), 1)
            doc.replace(remove_structure(doc.data, "visual_house", (4, 4)))
            draw()
            self.assertEqual(len(canvas.find_withtag("architecture_sprite")), 0)
            doc.undo()
            draw()
            self.assertEqual(len(canvas.find_withtag("architecture_sprite")), 1)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
