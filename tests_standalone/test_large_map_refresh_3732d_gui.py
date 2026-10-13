"""Xvfb end-to-end: 128² editor keeps minimap background while panning.

The real Editor, StudioPanels, Workspace and Canvas are exercised together.
A brush edit must invalidate the background; merely panning must not.
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import traceback
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import launch
from sporebound.model import Content


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tcl/Tk and Xvfb")
class LargeMapRefreshGuiTests(unittest.TestCase):
    def test_real_128_map_pan_does_not_rebuild_minimap_but_edit_does(self):
        import tkinter as tk

        source = Content.load(DEFAULT_CONTENT).to_dict()
        data = add_blank_mission(source, "performance_large",
                                 "Performance 128", 128, 128)
        large = next(m for m in data["missions"] if m["id"] == "performance_large")
        data["missions"] = [large] + [
            m for m in data["missions"] if m["id"] != "performance_large"]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "large-map.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            failures = []

            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)

            def drive(root):
                try:
                    root.report_callback_exception = (
                        lambda *error: failures.append(
                            "".join(traceback.format_exception(*error))))
                    root.update()
                    canvases = [
                        w for w in descendants(root) if isinstance(w, tk.Canvas)]
                    mini = next(w for w in canvases
                                if int(w.cget("width")) == 184 and
                                int(w.cget("height")) == 184)
                    main = next(w for w in canvases
                                if w is not mini and
                                len(w.find_all()) >= 128 * 128)
                    before = mini.find_all()
                    self.assertGreater(len(before), 1)
                    mini.event_generate("<Button-1>", x=90, y=120)
                    root.update()
                    after_pan = mini.find_all()
                    self.assertEqual(before[:-1], after_pan[:-1],
                                     "Navigation unexpectedly rebuilt terrain")
                    self.assertNotEqual(before[-1], after_pan[-1])

                    # A wall painted on an otherwise empty map adds a
                    # distinctive minimap square: the static scene must update.
                    main.event_generate("<Button-1>", x=110, y=108)
                    main.event_generate("<ButtonRelease-1>", x=110, y=108)
                    root.update()
                    after_edit = mini.find_all()
                    self.assertNotEqual(after_pan[:-1], after_edit[:-1],
                                        "Brush edit unexpectedly reused terrain")
                    self.assertFalse(failures, failures)
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.messagebox.showerror") as errors:
                launch(path)
                self.assertFalse(errors.called, errors.call_args_list)


if __name__ == "__main__":
    unittest.main()
