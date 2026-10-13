"""3.7.19B: direct-manipulation integration through the actual Tk editor."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import launch
from sporebound.iso_structures import place_structure
from sporebound.model import Content


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a real Tk display or Xvfb")
class StructureEditingGesturesTk(unittest.TestCase):
    def test_shift_drag_nudge_undo_and_cancel(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for widget in parent.winfo_children():
                yield widget
                yield from descendants(widget)

        with TemporaryDirectory() as tmp:
            mission_id = "structure_gestures"
            data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                     mission_id, "Atelier", 20, 20)
            data = place_structure(data, mission_id, "Maison", (5, 5))
            source = Path(tmp) / "input.json"
            target = Path(tmp) / "output.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            errors = []

            def save_and_read(button):
                button.invoke()
                return next(m for m in json.loads(
                    target.read_text(encoding="utf-8"))["missions"]
                            if m["id"] == mission_id)["structures"]

            def position(x, y):
                # Orthographic editor mode uses 54px square cells.
                return x * 54 + 27, y * 54 + 27

            def gesture(canvas, source_cell, target_cell, *, shift=False):
                x, y = position(*source_cell)
                tx, ty = position(*target_cell)
                canvas.event_generate("<Button-1>", x=x, y=y,
                                      state=1 if shift else 0)
                canvas.event_generate("<B1-Motion>", x=tx, y=ty,
                                      state=0x101 if shift else 0x100)
                canvas.event_generate("<ButtonRelease-1>", x=tx, y=ty,
                                      state=1 if shift else 0)

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    mission_box = next(
                        w for w in widgets if isinstance(w, ttk.Combobox)
                        and mission_id in w.cget("values"))
                    tool_box = next(
                        w for w in widgets if isinstance(w, ttk.Combobox)
                        and "Sélection structure" in w.cget("values"))
                    buttons = {w.cget("text"): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    mission_box.set(mission_id)
                    mission_box.event_generate("<<ComboboxSelected>>")
                    root.update()
                    tool_box.set("Sélection structure")

                    gesture(canvas, (6, 6), (12, 6), shift=True)
                    root.update()
                    structures = save_and_read(buttons["Enregistrer sous"])
                    self.assertEqual({tuple(v["anchor"]) for v in structures},
                                     {(5, 5), (11, 5)})
                    self.assertEqual(len({v["id"] for v in structures}), 2)

                    # Clicking a building without dragging must not add a
                    # document edit (one Undo removes exactly the copy).
                    x, y = position(12, 6)
                    canvas.event_generate("<Button-1>", x=x, y=y)
                    canvas.event_generate("<ButtonRelease-1>", x=x, y=y)
                    canvas.focus_set()
                    canvas.event_generate("<Right>")
                    root.update()
                    structures = save_and_read(buttons["Enregistrer sous"])
                    self.assertIn((12, 5), {tuple(v["anchor"]) for v in structures})
                    buttons["Annuler"].invoke()
                    root.update()
                    structures = save_and_read(buttons["Enregistrer sous"])
                    self.assertIn((11, 5), {tuple(v["anchor"]) for v in structures})
                    # Selection follows the same ID back through Undo.
                    canvas.event_generate("<Right>")
                    root.update()
                    structures = save_and_read(buttons["Enregistrer sous"])
                    self.assertIn((12, 5), {tuple(v["anchor"]) for v in structures})

                    # Escape during dragging must not apply the pending move.
                    x, y = position(6, 6)
                    tx, ty = position(7, 8)
                    canvas.event_generate("<Button-1>", x=x, y=y)
                    canvas.event_generate("<B1-Motion>", x=tx, y=ty,
                                          state=0x100)
                    self.assertTrue(canvas.find_withtag("structure_drag_preview"))
                    canvas.event_generate("<Escape>")
                    canvas.event_generate("<ButtonRelease-1>", x=tx, y=ty)
                    root.update()
                    structures = save_and_read(buttons["Enregistrer sous"])
                    self.assertIn((5, 5), {tuple(v["anchor"]) for v in structures})
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.filedialog.asksaveasfilename",
                       return_value=str(target)), \
                 patch("tkinter.messagebox.showerror") as dialogs:
                launch(source)
                dialogs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
