"""Opt-in real Tk smoke test of the strategic command GUI under Xvfb."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from examples.siege_fronts import siege_session


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk display, e.g. xvfb-run")
class StrategicGUITests(unittest.TestCase):
    def test_switch_turn_and_verified_checkpoint(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.strategic_ui import launch

        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "command.json"
            session = siege_session(contested=True)
            errors = []

            def children(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from children(child)

            def inspect(root):
                try:
                    root.report_callback_exception = lambda *error: errors.append(error)
                    root.update()
                    widgets = list(children(root))
                    buttons = {w.cget("text"): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    trees = [w for w in widgets if isinstance(w, ttk.Treeview)]
                    self.assertGreaterEqual(len(trees), 2)
                    self.assertEqual(len(trees[0].get_children()), 5)
                    buttons["Jouer tactique"].invoke()  # start battle from preset
                    buttons["Tour stratégique +1"].invoke()
                    root.update()
                    self.assertEqual(session.timeline.turn, 1)
                    buttons["Enregistrer"].invoke()
                    self.assertTrue(checkpoint.exists())
                    buttons["Tour stratégique +1"].invoke()
                    self.assertEqual(session.timeline.turn, 2)
                    buttons["Reprendre"].invoke()
                    root.update()
                    displayed = "\n".join(w.get("1.0", "end") for w in widgets
                                          if isinstance(w, tk.Text))
                    self.assertIn("front_resolved", displayed)
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", inspect), \
                 patch("tkinter.filedialog.asksaveasfilename",
                       return_value=str(checkpoint)), \
                 patch("tkinter.filedialog.askopenfilename",
                       return_value=str(checkpoint)), \
                 patch("tkinter.messagebox.showerror") as error:
                resumed = launch(session)
                self.assertEqual(resumed.timeline.turn, 1)
                error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
