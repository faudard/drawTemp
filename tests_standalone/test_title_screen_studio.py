"""Optional end-to-end Tk drag test for the Title Screen Studio canvas."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1", "Requires Tk display")
class TitleScreenStudioGuiTests(unittest.TestCase):
    def test_drag_undo_redo_and_apply_to_project(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.__main__ import DEFAULT_CONTENT
        from sporebound.game_project import GameProject
        from sporebound.model import Content
        from sporebound.tactical_rpg3 import authored_rules_for_document
        from sporebound.title_screen_studio import TitleScreenStudio
        from sporebound.title_screen_settings import settings_for

        raw = json.loads(Path(DEFAULT_CONTENT).read_text(encoding="utf-8"))
        content = Content.from_dict(raw, rules=authored_rules_for_document(raw))
        root = tk.Tk()
        try:
            root.geometry("1500x950")
            notebook = ttk.Notebook(root)
            notebook.pack(fill="both", expand=True)
            with TemporaryDirectory() as directory:
                owner = SimpleNamespace(
                    tk=tk, ttk=ttk, project=GameProject.default(content),
                    project_path=Path(directory) / "sample.game.json",
                    title=tk.StringVar(), subtitle=tk.StringVar(),
                    project_status=ttk.Label(root),
                    _run=lambda operation: operation(),
                    _content=lambda: content,
                    refresh=lambda: None,
                    save_project=lambda: None,
                )
                studio = TitleScreenStudio(owner, notebook)
                notebook.select(studio.tab)
                studio.load()
                root.update()
                original = studio._last_boxes["new"]
                ox, oy, scale = studio._preview_transform
                x = round(ox + (original[0] + 20) * scale)
                y = round(oy + (original[1] + 20) * scale)
                studio.canvas.event_generate("<ButtonPress-1>", x=x, y=y)
                studio.canvas.event_generate("<B1-Motion>",
                                             x=x-100, y=y+35)
                studio.canvas.event_generate("<ButtonRelease-1>",
                                             x=x-100, y=y+35)
                root.update()
                self.assertIn("new", studio._positions)
                moved = studio._positions["new"]
                self.assertLess(moved[0], original[0] / 1160)
                self.assertTrue(studio.pending())
                studio.undo_move()
                self.assertEqual(studio._positions, {})
                studio.redo_move()
                self.assertEqual(studio._positions["new"], moved)
                studio.apply()
                self.assertEqual(settings_for(owner.project)["positions"]["new"], moved)
                studio.reset_selected()
                self.assertEqual(studio._positions, {})
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
