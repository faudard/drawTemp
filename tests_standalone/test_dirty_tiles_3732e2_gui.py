"""3.7.32E2 real Tk parity with static actors, tall props and roofs.

Same canonical renderer supplies reference; compare full Canvas item type,
coordinates, style/tag properties and draw order, not screenshots alone.
"""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.editor_render_cache import EditorRenderCache
from sporebound.iso_map import render_isometric
from sporebound.iso_structures import place_structure
from sporebound.model import Content


@unittest.skipUnless(os.getenv("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk under Xvfb")
class OcclusionDirtyTileGuiTests(unittest.TestCase):
    def check_scene(self, doc, mid, canvas, reference, cache, revision,
                    *, selected=None, zoom=54, expected="dirty_tiles"):
        mission = Content.from_dict(doc.data).missions[mid]
        options = dict(cell_size=zoom, layers={}, selected_cell=selected,
                       selected_tiles=())
        cache.draw(mission.board, mission, mission.units,
                   scene_revision=(revision, mid), **options)
        render_isometric(reference, mission.board, mission, mission.units,
                         **options)

        def items(view):
            return [
                (view.type(i), view.coords(i),
                 {k: row[-1] for k, row in view.itemconfigure(i).items()})
                for i in view.find_all()
            ]

        self.assertEqual(items(canvas), items(reference))
        self.assertEqual(str(canvas.cget("scrollregion")),
                         str(reference.cget("scrollregion")))
        self.assertEqual(cache.stats["fast_path"], expected)
        return cache.stats

    def test_actors_and_high_decor_at_both_large_scales(self):
        import tkinter as tk
        for size in (65, 128):
            with self.subTest(size=size):
                root = tk.Tk()
                try:
                    foreground = tk.Canvas(root)
                    reference = tk.Canvas(root)
                    cache = EditorRenderCache(foreground)
                    mid = "occlusion"
                    data = add_blank_mission(
                        Content.load(DEFAULT_CONTENT).to_dict(), mid,
                        "Art", size, size)
                    doc = Document(Content.from_dict(data))
                    self.check_scene(
                        doc, mid, foreground, reference, cache, 1,
                        expected="full")
                    # The default player stands at x=1, y=size-2.
                    # Paint immediately behind this actor; the fast path must
                    # restore its body and label to their original depth.
                    doc.paint_many(mid, [(2, size-2)], "surface:water")
                    stats = self.check_scene(
                        doc, mid, foreground, reference, cache, 2)
                    self.assertEqual(stats["dirty_cells"], 9)
                    doc.paint_many(mid, [(3, size-3)], "feature:tree")
                    self.check_scene(doc, mid, foreground, reference, cache, 3)
                    doc.paint_many(mid, [(3, size-3)], "feature:arch")
                    self.check_scene(doc, mid, foreground, reference, cache, 4)
                    doc.undo()
                    self.check_scene(doc, mid, foreground, reference, cache, 5)
                finally:
                    root.destroy()

    def test_authored_house_roof_cutaway_and_nearby_terrain(self):
        import tkinter as tk
        root = tk.Tk()
        try:
            foreground = tk.Canvas(root)
            reference = tk.Canvas(root)
            cache = EditorRenderCache(foreground)
            mid = "occlusion"
            data = add_blank_mission(
                Content.load(DEFAULT_CONTENT).to_dict(), mid, "Art", 65, 65)
            data = place_structure(data, mid, "Maison", (15, 15), 0)
            doc = Document(Content.from_dict(data))
            mission = Content.from_dict(doc.data).missions[mid]
            building = mission.structures[0]
            anchor = tuple(building["anchor"])
            self.check_scene(doc, mid, foreground, reference, cache, 1,
                             selected=anchor, expected="full")
            # Paint just outside the built footprint, but behind its sprite.
            doc.paint_many(mid, [(14, 15)], "surface:water")
            stats = self.check_scene(
                doc, mid, foreground, reference, cache, 2, selected=anchor)
            self.assertGreater(stats["architecture_instances"], 0)
            doc.paint_many(mid, [(14, 16)], "feature:tree")
            self.check_scene(
                doc, mid, foreground, reference, cache, 3, selected=anchor)
            doc.undo()
            self.check_scene(
                doc, mid, foreground, reference, cache, 4, selected=anchor)
            # A cutaway change and terrain edit together are conservatively
            # repainted in full, not allowed through a stale overlay.
            doc.paint_many(mid, [(14, 17)], "surface:water")
            self.check_scene(
                doc, mid, foreground, reference, cache, 5,
                selected=(3, 3), expected="full")
        finally:
            root.destroy()

    def test_legacy_architecture_identity_and_height_fallback(self):
        import tkinter as tk
        root = tk.Tk()
        try:
            foreground = tk.Canvas(root)
            reference = tk.Canvas(root)
            cache = EditorRenderCache(foreground)
            mid = "occlusion"
            data = add_blank_mission(
                Content.load(DEFAULT_CONTENT).to_dict(), mid, "Art", 65, 65)
            data = place_structure(data, mid, "Maison", (12, 12), 0)
            doc = Document(Content.from_dict(data))
            self.check_scene(doc, mid, foreground, reference, cache, 1,
                             expected="full")
            doc.paint_many(mid, [(9, 12)], "height+")
            self.check_scene(doc, mid, foreground, reference, cache, 2,
                             expected="full")
            # The roof and facade do not go stale across zoom changes.
            self.check_scene(doc, mid, foreground, reference, cache, 3,
                             zoom=96, expected="full")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
