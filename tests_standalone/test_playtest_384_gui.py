"""3.8.4 Player opt-in and Studio report viewing under real Tk/Xvfb."""
import os
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch as launch_studio
from sporebound.player_app import launch as launch_player


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk under Xvfb")
class HumanPlaytestGUITests(unittest.TestCase):
    def test_player_options_are_opt_in_and_can_be_disabled(self):
        import tkinter as tk
        from tkinter import ttk
        failures = []

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        def drive(root):
            try:
                root.report_callback_exception = lambda *args: failures.append(args)
                buttons = [w for w in descendants(root) if isinstance(w, ttk.Button)]
                option = next(w for w in buttons if w.cget("text") == "Options")
                option.invoke()
                root.update()
                checkbox = next(w for w in descendants(root)
                                if isinstance(w, ttk.Checkbutton) and
                                "playtests" in w.cget("text"))
                self.assertFalse(checkbox.instate(["selected"]))
                checkbox.invoke()
                root.update()
                self.assertTrue(checkbox.instate(["selected"]))
                checkbox.invoke()
                self.assertFalse(checkbox.instate(["selected"]))
                self.assertFalse(failures)
            finally:
                root.destroy()

        with patch.object(tk.Tk, "mainloop", drive), \
             patch("tkinter.messagebox.showerror") as errors:
            launch_player(DEFAULT_CONTENT)
            errors.assert_not_called()

    def test_studio_playtest_lab_import_and_row_inspection(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        errors = []
        sample = {
            "kind": "human_playtest", "schema": 1, "opt_in": True,
            "sessions": [{
                "mission": "garden", "objective": "eliminate",
                "outcome": "victory", "partial_capture": False,
                "duration_seconds": 780,
                "duration_basis": "wall_elapsed_monotonic_including_idle",
                "ct_start": 0, "ct_end": 90,
                "command_kinds": {"act": 2, "end": 1},
                "accepted_actions": {"combat_command": 3},
                "objective_hold_ticks": 0, "goal_occupied": False,
                "surviving_units": 2, "damage_observed": 8,
                "healing_observed": 2, "truncated_events": 0,
                "events": [{"seconds": 250, "event": "combat_command",
                            "command": {"kind": "act"}, "team": "player",
                            "tick": 27}],
            }],
        }

        def drive(root):
            try:
                root.report_callback_exception = lambda *args: errors.append(args)
                root.update()
                books = [w for w in descendants(root)
                         if isinstance(w, ttk.Notebook)]
                book = next(w for w in books if
                            "Playtest Lab" in [w.tab(tab, "text") for tab in w.tabs()])
                tab = root.nametowidget(
                    next(t for t in book.tabs()
                         if book.tab(t, "text") == "Playtest Lab"))
                book.select(tab)
                panels = [w for w in descendants(tab)]
                self.assertTrue(any(isinstance(w, ttk.Button) and
                                    w.cget("text") == "Importer playtests JSON"
                                    for w in panels))
                from types import SimpleNamespace
                from sporebound.studio_playtest import PlaytestStudio
                # Also exercise the actual model rendering with a real Tk
                # notebook. No manual JSON write or fake engine simulation.
                model = PlaytestStudio(
                    SimpleNamespace(tk=tk, ttk=ttk, dialogs=None), book)
                model.set_report(sample)
                self.assertEqual(len(model.rows.get_children()), 1)
                model.rows.selection_set(model.rows.get_children()[0])
                model.select()
                self.assertIn("garden", model.summary.cget("text"))
                self.assertIn("13.0", model.summary.cget("text"))
                self.assertGreater(len(model.canvas.find_all()), 0)
                self.assertFalse(errors)
            finally:
                root.destroy()

        with patch.object(tk.Tk, "mainloop", drive), \
             patch("tkinter.messagebox.showerror") as modal:
            launch_studio(DEFAULT_CONTENT)
            modal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
