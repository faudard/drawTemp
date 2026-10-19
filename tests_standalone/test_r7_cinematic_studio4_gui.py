"""R7.19 real Tk Studio gate: key handles, contextual tabs and transaction UX."""
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
                     "Requires Tk/Xvfb display")
class CinematicStudio4GUITests(unittest.TestCase):
    def test_create_key_edit_undo_redo_preview_retime_and_save(self):
        import tkinter as tk
        from tkinter import ttk
        root = tk.Tk()
        root.geometry("1400x1000")
        root.withdraw()
        studio = None
        try:
            with TemporaryDirectory() as folder:
                content = Content.load(DEFAULT_CONTENT)
                owner = SimpleNamespace(
                    tk=tk, ttk=ttk, project=GameProject.default(content),
                    project_path=Path(folder)/"studio.game.json",
                    project_status=Mock(), save_project=Mock(),
                    _content=lambda: content,
                    _run=lambda fn: fn(), capture_history=Mock())
                notebook = ttk.Notebook(root)
                notebook.pack(fill="both", expand=True)
                studio = CinematicStudio(owner, notebook)
                studio.reset_project()
                root.update_idletasks()
                self.assertEqual(len(studio.inspector_tabs.tabs()), 3)
                studio.vars["cid"].set("r719_demo")
                studio.vars["name"].set("R7.19 Démo")
                studio.vars["trigger"].set("campaign_start")
                studio.vars["target"].set("main")
                studio.vars["length"].set("4000")
                studio.create_clip()
                self.assertEqual(float(studio.preview_scale.cget("to")), 4000.)
                studio.vars["eid"].set("walk")
                studio.vars["kind"].set("actor")
                studio.vars["start"].set("0")
                studio.vars["duration"].set("2000")
                studio.vars["subject"].set("jeanne")
                studio.add_event()
                studio.cursor.set(1000)
                studio.add_key()
                event = studio._event()
                self.assertEqual(event["keyframes"][0]["at_ms"], 1000)
                studio._load_event()
                studio.update_event()
                self.assertEqual(studio._event()["keyframes"][0]["at_ms"], 1000,
                                 "Applying the inspector must not discard keyframes")
                studio.selected_key_ms = 1000
                studio.vars["key_time"].set("800")
                studio.vars["key_x"].set("1.2")
                studio.vars["key_y"].set("0.5")
                studio.update_key()
                self.assertEqual(studio._event()["keyframes"][0]["pos"],
                                 [1.2, .5])
                self.assertEqual(studio._event()["keyframes"][0]["at_ms"], 800)
                studio.undo()
                self.assertEqual(studio._event()["keyframes"][0]["at_ms"], 1000)
                studio.redo()
                self.assertEqual(studio._event()["keyframes"][0]["at_ms"], 800)
                studio.vars["duration"].set("1600")
                studio.resize_selected()
                self.assertEqual(studio._event()["keyframes"][0]["at_ms"], 640)
                studio.duplicate_event()
                self.assertEqual(len(studio._clip()["events"]), 2)
                self.assertNotEqual(studio._clip()["events"][0]["id"],
                                    studio._clip()["events"][1]["id"])
                studio.cursor.set(1000)
                root.update_idletasks()
                self.assertTrue(studio._positions)
                self.assertTrue(studio._key_handles)
                self.assertIn("Mixage", studio.audio_caption.get())
                owner.project.save(owner.project_path, content)
                project = GameProject.load(owner.project_path, content)
                self.assertEqual(len(project.cinematics[0]["events"]), 2)
                # Applying an unchanged inspector event is a no-op. The six
                # actual mutations each append one global history checkpoint;
                # undo/redo and a no-op must never duplicate checkpoints.
                self.assertEqual(owner.capture_history.call_count, 6)
                # Undo/redo themselves do not append duplicate history items.
        finally:
            if studio is not None and studio.preview_renderer is not None:
                studio.preview_renderer.dispose()
            root.destroy()

    def test_invalid_key_edit_does_not_write_project_or_history(self):
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
                project_status=Mock(), save_project=Mock(),
                _content=lambda: content,
                _run=lambda fn: fn(), capture_history=Mock())
            notebook = ttk.Notebook(root)
            notebook.pack()
            studio = CinematicStudio(owner, notebook)
            studio.reset_project()
            studio.vars["cid"].set("valid")
            studio.vars["name"].set("Validation")
            studio.vars["trigger"].set("campaign_start")
            studio.vars["target"].set("main")
            studio.create_clip()
            studio.vars["eid"].set("walk")
            studio.vars["kind"].set("actor")
            studio.vars["subject"].set("jeanne")
            studio.vars["duration"].set("1800")
            studio.add_event()
            studio.cursor.set(600)
            studio.add_key()
            before = owner.project.to_dict()
            history = len(studio.undo_stack)
            studio.selected_key_ms = 600
            studio.vars["key_time"].set("0")
            with self.assertRaises(RuleError):
                studio.update_key()
            self.assertEqual(owner.project.to_dict(), before)
            self.assertEqual(len(studio.undo_stack), history)
        finally:
            if studio is not None and studio.preview_renderer is not None:
                studio.preview_renderer.dispose()
            root.destroy()


if __name__ == "__main__":
    unittest.main()
