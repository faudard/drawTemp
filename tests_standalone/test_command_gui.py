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


    def test_graphical_rescue_and_abandon_order(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.strategic_ui import launch

        session = siege_session(contested=True)
        session.set_doctrine("walls", "hold")
        session.send_reserves("walls", [
            {"id": "gui_reserve", "name": "GUI Reserve",
             "team": "player", "pos": [3, 6]}])
        session.advance()
        self.assertTrue(session.logistics.convoy("convoy_1")["stranded"])
        errors = []

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        def inspect(root):
            try:
                root.report_callback_exception = lambda *error: errors.append(error)
                root.update()
                controls = list(descendants(root))
                buttons = {w.cget("text"): w for w in controls
                           if isinstance(w, ttk.Button)}
                treeviews = [w for w in controls if isinstance(w, ttk.Treeview)]
                convoys = next(t for t in treeviews if "convoy_1" in t.get_children())
                convoys.selection_set("convoy_1")
                buttons["Combat de secours"].invoke()
                root.update()
                self.assertIn("convoy_1", session.rescue_battles)
                action = next(w for w in controls if isinstance(w, ttk.Entry)
                              and w.get() == '{"kind":"start_battle"}')
                action.delete(0, "end")
                action.insert(0, '{"kind":"end"}')
                buttons["Jouer tactique"].invoke()
                self.assertEqual(len(session.rescue_battles["convoy_1"].commands), 1)
                buttons["Abandonner"].invoke()
                self.assertEqual(session.rescue_outcomes["convoy_1"], "abandoned")
                self.assertFalse(session.rescue_battles)
                self.assertEqual(errors, [])
            finally:
                root.destroy()

        with patch.object(tk.Tk, "mainloop", inspect), \
             patch("tkinter.messagebox.showerror") as showerror:
            launch(session)
            showerror.assert_not_called()


    def test_graphical_evacuate_and_pursue(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.strategic_ui import launch

        session = siege_session(contested=True, decisions=True)
        session.set_doctrine("walls", "hold")
        session.send_reserves("walls", [
            {"id": "gui_choices", "name": "GUI Choices",
             "team": "player", "pos": [3, 6]}])
        session.advance()

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        def inspect(root):
            try:
                root.update()
                all_widgets = list(descendants(root))
                buttons = {w.cget("text"): w for w in all_widgets
                           if isinstance(w, ttk.Button)}
                convoys = next(w for w in all_widgets if isinstance(w, ttk.Treeview)
                               and "convoy_1" in w.get_children())
                convoys.selection_set("convoy_1")
                buttons["Évacuer équipage"].invoke()
                self.assertEqual(session.rescue_outcomes["convoy_1"], "evacuated")
                self.assertIn("convoy_1", session.pursuit_targets)
                self.assertEqual(convoys.selection(), ("convoy_1",))
                buttons["Poursuivre pillards"].invoke()
                self.assertIn("convoy_1", session.pursuit_battles)
                editor = next(w for w in all_widgets if isinstance(w, ttk.Entry)
                              and w.get() == '{"kind":"start_battle"}')
                editor.delete(0, "end")
                editor.insert(0, '{"kind":"end"}')
                buttons["Jouer tactique"].invoke()
                self.assertEqual(len(session.pursuit_battles["convoy_1"].commands), 1)
                buttons["Abandon poursuite"].invoke()
                self.assertEqual(session.pursuit_outcomes["convoy_1"], "abandoned")
            finally:
                root.destroy()

        with patch.object(tk.Tk, "mainloop", inspect), \
             patch("tkinter.messagebox.showerror") as showerror:
            launch(session)
            showerror.assert_not_called()


if __name__ == "__main__":
    unittest.main()
