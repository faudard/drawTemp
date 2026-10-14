"""R7.20 real Tk multi-selection, clipboard, shortcuts and history smoke."""
from copy import deepcopy
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.studio_cinematics import CinematicStudio


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires the Tk editor and Xvfb")
class CinematicBatchGuiTests(unittest.TestCase):
    def test_multiselect_copy_paste_shift_undo_redo_save_and_guards(self):
        import tkinter as tk
        from tkinter import ttk
        root = tk.Tk()
        root.geometry("1400x950")
        root.withdraw()
        studio = None
        try:
            with TemporaryDirectory() as folder:
                content = Content.load(DEFAULT_CONTENT)
                owner = SimpleNamespace(
                    tk=tk, ttk=ttk, project=GameProject.default(content),
                    project_path=Path(folder)/"studio.game.json",
                    project_status=Mock(), _content=lambda: content,
                    _run=lambda fn: fn(), capture_history=Mock())
                tabs = ttk.Notebook(root)
                tabs.pack(fill="both", expand=True)
                studio = CinematicStudio(owner, tabs)
                studio.reset_project()
                for cid in ("village", "castle"):
                    studio.vars["cid"].set(cid)
                    studio.vars["name"].set(cid.title())
                    studio.vars["trigger"].set("campaign_start")
                    studio.vars["target"].set("main")
                    studio.vars["length"].set("6500")
                    studio.create_clip()
                studio.clip_id = "village"
                studio.refresh()
                for eid, kind, start, duration in (
                        ("jeanne", "actor", 500, 1200),
                        ("parole", "dialogue", 1800, 900),
                        ("score", "sound", 300, 3500)):
                    studio.vars["eid"].set(eid)
                    studio.vars["kind"].set(kind)
                    studio.vars["start"].set(str(start))
                    studio.vars["duration"].set(str(duration))
                    studio.vars["subject"].set("jeanne" if kind == "actor" else
                                               "Jeanne" if kind == "dialogue"
                                               else "theme")
                    studio.vars["bus"].set("music")
                    studio.add_event()
                studio.events.selection_clear(0, "end")
                studio.events.selection_set(0)
                studio.events.selection_set(1)
                studio._on_event()
                self.assertEqual(set(studio.selected_event_ids),
                                 {"jeanne", "score"})
                self.assertEqual(studio._keyboard_action(studio.copy_selected), "break")
                self.assertEqual(len(studio.clipboard["events"]), 2)
                original = deepcopy(studio._clip())
                history = len(studio.undo_stack)
                studio.vars["group_shift"].set("200")
                studio.shift_selected()
                self.assertEqual(len(studio.undo_stack), history+1)
                moved = {e["id"]: e["start_ms"] for e in studio._clip()["events"]}
                self.assertEqual(moved["jeanne"], 700)
                self.assertEqual(moved["score"], 500)
                studio.undo()
                self.assertEqual(studio._clip()["events"], original["events"])
                studio.redo()
                self.assertEqual(
                    {e["id"]: e["start_ms"] for e in studio._clip()["events"]},
                    moved)
                from types import SimpleNamespace as Pointer
                # Ctrl-click toggles another track without mutating project.
                talk = next(row for row in studio._positions
                            if row[4] == "parole")
                click = Pointer(x=(talk[0]+talk[1])/2,
                                y=talk[2]+10, state=4)
                before_select = owner.project.to_dict()
                studio._press(click)
                self.assertEqual(set(studio.selected_event_ids),
                                 {"jeanne", "score", "parole"})
                studio._press(click)
                self.assertEqual(set(studio.selected_event_ids),
                                 {"jeanne", "score"})
                self.assertEqual(owner.project.to_dict(), before_select)
                # Dragging a selected block moves both lanes in ONE revision.
                actor_row = next(row for row in studio._positions
                                 if row[4] == "jeanne")
                start_x = (actor_row[0]+actor_row[1])/2
                pressed = Pointer(x=start_x, y=actor_row[2]+10, state=0)
                depth_before_drag = len(studio.undo_stack)
                studio._press(pressed)
                studio._drag_motion(Pointer(x=start_x+10, y=pressed.y,
                                            state=0))
                self.assertTrue(studio.timeline.find_withtag("drag-preview"))
                studio._release(Pointer(x=start_x+10, y=pressed.y, state=0))
                self.assertEqual(len(studio.undo_stack), depth_before_drag+1)
                self.assertEqual(
                    {e["id"]: e["start_ms"] for e in studio._clip()["events"]
                     if e["id"] in ("jeanne", "score")},
                    {"jeanne": 900, "score": 700})
                studio.undo()
                self.assertEqual(
                    {e["id"]: e["start_ms"] for e in studio._clip()["events"]},
                    moved)
                studio.clip_id = "castle"
                studio.event_id = ""
                studio.selected_event_ids = ()
                studio.refresh()
                studio.cursor.set(1500)
                before_paste = len(studio.undo_stack)
                studio.paste_selected()
                self.assertEqual(len(studio.undo_stack), before_paste+1)
                self.assertEqual(len(studio._clip()["events"]), 2)
                self.assertEqual(len(studio.selected_event_ids), 2)
                self.assertTrue(all(e["id"] in studio.selected_event_ids
                                    for e in studio._clip()["events"]))
                self.assertEqual(
                    [e["start_ms"] for e in studio._clip()["events"]],
                    [1700, 1500])  # actor starts 200ms after score
                original_clipboard = deepcopy(studio.clipboard)
                before = owner.project.to_dict()
                before_history = len(studio.undo_stack)
                studio.cursor.set(6300)
                with self.assertRaises(RuleError):
                    studio.paste_selected()
                self.assertEqual(owner.project.to_dict(), before)
                self.assertEqual(len(studio.undo_stack), before_history)
                self.assertEqual(studio.clipboard, original_clipboard)
                studio.cursor.set(2000)
                studio.cut_selected()
                self.assertEqual(len(studio._clip()["events"]), 0)
                studio.undo()
                self.assertEqual(len(studio._clip()["events"]), 2)
                studio.redo()
                self.assertEqual(len(studio._clip()["events"]), 0)
                # Clipboard lives in memory and can be pasted after Undo/Redo.
                studio.paste_selected()
                self.assertEqual(len(studio._clip()["events"]), 2)
                owner.project.save(owner.project_path, content)
                restored = GameProject.load(owner.project_path, content)
                self.assertEqual(len(next(c for c in restored.cinematics
                                          if c["id"] == "castle")["events"]), 2)
                self.assertIsNotNone(studio.events.bind("<Control-KeyPress-c>"))
        finally:
            if studio is not None and studio.preview_renderer is not None:
                studio.preview_renderer.dispose()
            root.destroy()

    def test_cinematic_undo_uses_global_studio_history_when_available(self):
        import tkinter as tk
        from tkinter import ttk
        root = tk.Tk()
        root.withdraw()
        studio = None
        try:
            content = Content.load(DEFAULT_CONTENT)
            owner = SimpleNamespace(
                tk=tk, ttk=ttk, project=GameProject.default(content),
                project_path=Path.cwd()/"unused.game.json",
                project_status=Mock(), _content=lambda: content,
                _run=lambda fn: fn(), capture_history=Mock(),
                history=object(), undo_global=Mock(), redo_global=Mock())
            tabs = ttk.Notebook(root)
            tabs.pack()
            studio = CinematicStudio(owner, tabs)
            studio.reset_project()
            studio.undo()
            studio.redo()
            owner.undo_global.assert_called_once_with()
            owner.redo_global.assert_called_once_with()
        finally:
            if studio is not None and studio.preview_renderer is not None:
                studio.preview_renderer.dispose()
            root.destroy()


if __name__ == "__main__":
    unittest.main()
