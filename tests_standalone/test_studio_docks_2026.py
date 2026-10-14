"""3.7 Studio UX 2.0: reversible dock and layout preferences gates."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import unittest

from sporebound.studio_docks import DOCKS, DockPreferences


class DockPrefsTests(unittest.TestCase):
    def test_roundtrip_atomic_and_strict_boolean_values(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "project.workspace.docks.json"
            prefs = DockPreferences(path)
            self.assertEqual(prefs.load(), {})
            prefs.save({"explorer": True, "inspector": False,
                        "bottom": True, "unknown": "nope"})
            self.assertEqual(prefs.load(), {"explorer": True, "inspector": False,
                                           "bottom": True})
            self.assertEqual(set(json.loads(path.read_text())), set(DOCKS))
            self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())
            path.write_text(json.dumps({"explorer": 1, "inspector": "false",
                                        "bottom": False}), encoding="utf-8")
            self.assertEqual(prefs.load(), {"bottom": False})
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(prefs.load(), {})


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Tk/Xvfb required")
class StudioDocksTkTests(unittest.TestCase):
    def test_hide_restore_focus_and_child_identity(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.studio_docks import StudioDocks

        root = tk.Tk()
        try:
            root.geometry("1200x780")
            work = ttk.Panedwindow(root, orient="horizontal")
            work.pack(fill="both", expand=True)
            left = ttk.Frame(work)
            middle = ttk.Panedwindow(work, orient="vertical")
            right = ttk.Frame(work)
            work.add(left, weight=1)
            work.add(middle, weight=4)
            work.add(right, weight=2)
            canvas = ttk.Frame(middle)
            bottom = ttk.Frame(middle)
            middle.add(canvas, weight=4)
            middle.add(bottom, weight=1)
            docks = StudioDocks(root, work, middle, left, right, bottom, tk)
            original = (str(left), str(right), str(bottom), str(canvas))
            root.update()

            docks.set_visible("inspector", False)
            root.update()
            self.assertFalse(docks.visible("inspector"))
            self.assertEqual(len(work.panes()), 2)
            self.assertEqual(str(canvas), original[3])

            docks.set_focus(True)
            root.update()
            self.assertTrue(docks.focus_var.get())
            self.assertEqual(tuple(work.panes()), (str(middle),))
            self.assertEqual(tuple(middle.panes()), (str(canvas),))
            self.assertEqual(docks.persistence(), {
                "explorer": True, "inspector": False, "bottom": True
            })

            # Tcl checkbuttons change their variable BEFORE invoking command.
            docks.focus_var.set(False)
            docks.set_focus(False)
            root.update()
            self.assertTrue(docks.visible("explorer"))
            self.assertFalse(docks.visible("inspector"))
            self.assertTrue(docks.visible("bottom"))
            docks.toggle("inspector")
            root.update()
            self.assertEqual(tuple(work.panes()),
                             (str(left), str(middle), str(right)))
            self.assertEqual(tuple(middle.panes()), (str(canvas), str(bottom)))

            docks.restore({"explorer": False, "inspector": True,
                           "bottom": False})
            root.update()
            self.assertFalse(docks.visible("explorer"))
            self.assertTrue(docks.visible("inspector"))
            self.assertFalse(docks.visible("bottom"))
            self.assertEqual(str(canvas), original[3])
            self.assertEqual(len(DOCKS), 3)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
