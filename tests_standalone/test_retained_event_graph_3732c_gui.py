"""Real-Tk canvas parity for retained event graph selection updates (3.7.32C)."""
import os
from types import SimpleNamespace
import unittest

from scripts.profile_scale_3732 import make_event_graph
from sporebound.studio_event_graph import EventGraphStudio


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a Tk display/Xvfb")
class RetainedEventGraphTests(unittest.TestCase):
    def test_selection_and_preview_reuse_items_and_equal_full_repaint(self):
        import tkinter as tk
        root = tk.Tk()
        try:
            root.geometry("900x600")
            data, mission = make_event_graph(8)
            canvas = tk.Canvas(root, width=840, height=550)
            canvas.pack()
            root.update_idletasks()
            owner = SimpleNamespace(
                doc=lambda: SimpleNamespace(data=data),
                mission=lambda: mission,
            )
            editor = EventGraphStudio.__new__(EventGraphStudio)
            editor.owner = owner
            editor.canvas = canvas
            editor.zoom = tk.StringVar(root, value="100%")
            editor.event_id = tk.StringVar(root, value="")
            editor.action_index = None
            editor.last_preview = None
            editor.status = tk.StringVar(root)
            editor._rendered_graph = None
            editor._rendered_scale = None
            editor._node_items = {}
            editor._node_styles = {}
            editor._rendered_item_count = 0

            def scene():
                return tuple((
                    canvas.type(item),
                    tuple(canvas.coords(item)),
                    tuple(canvas.gettags(item)),
                    canvas.itemcget(item, "fill"),
                    canvas.itemcget(item, "outline") if
                    canvas.type(item) == "rectangle" else "",
                    canvas.itemcget(item, "width") if
                    canvas.type(item) != "text" else "",
                    canvas.itemcget(item, "text") if
                    canvas.type(item) == "text" else "",
                ) for item in canvas.find_all())

            editor.draw()
            original_ids = canvas.find_all()
            self.assertGreater(len(original_ids), 15)
            editor.draw()  # identical graph: no new items
            self.assertEqual(canvas.find_all(), original_ids)

            editor.event_id.set("scale_trigger_000")
            editor.draw()
            self.assertEqual(canvas.find_all(), original_ids)
            condition_rect = editor._node_items[("scale_trigger_000", "condition")]
            self.assertEqual(canvas.itemcget(condition_rect, "outline"), "#2563eb")
            editor.action_index = 0
            editor.draw()
            self.assertEqual(canvas.find_all(), original_ids)

            editor.action_index = None
            editor.last_preview = {
                "event_id": "scale_trigger_000", "error": False, "fired": True,
            }
            editor.draw()
            self.assertEqual(canvas.find_all(), original_ids)
            self.assertEqual(canvas.itemcget(condition_rect, "fill"), "#bbf7d0")
            retained = scene()

            # Compare exact types, coordinates, painter order, tags and styles.
            editor._rendered_graph = None
            editor.draw()
            self.assertEqual(scene(), retained)
            self.assertNotEqual(canvas.find_all(), original_ids)

            # Data changed in place: label rebuild must not serve stale text.
            mission_row = next(row for row in data["missions"]
                               if row["id"] == mission)
            mission_row["triggers"][0]["actions"][0]["text"] = "Revised text"
            before_ids = canvas.find_all()
            editor.draw()
            self.assertNotEqual(canvas.find_all(), before_ids)
            self.assertTrue(any(
                "Revised text" in canvas.itemcget(item, "text")
                for item in canvas.find_all() if canvas.type(item) == "text"))

            before_ids = canvas.find_all()
            editor.zoom.set("130%")
            editor.draw()
            self.assertNotEqual(canvas.find_all(), before_ids)
            before_ids = canvas.find_all()
            canvas.create_text(3, 3, text="external")
            editor.draw()
            self.assertNotEqual(canvas.find_all(), before_ids)
            self.assertFalse(any(
                "external" == canvas.itemcget(item, "text")
                for item in canvas.find_all() if canvas.type(item) == "text"))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
