"""Tk Audio Studio smoke test; run with SPOREBOUND_GUI_SMOKE=1 under Xvfb."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.studio_audio import AudioStudio


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a Tk display")
class AudioStudioGuiTests(unittest.TestCase):
    def test_import_binding_diagnostics_and_project_save(self):
        import tkinter as tk
        from tkinter import ttk
        with TemporaryDirectory() as folder:
            path = Path(folder)
            source = path / "village.wav"
            source.write_bytes(b"RIFF" + b"\0" * 4 + b"WAVE" + b"fake-audio")
            root = tk.Tk()
            root.withdraw()
            try:
                content = Content.load(DEFAULT_CONTENT)
                project = GameProject.default(content)
                notebook = ttk.Notebook(root)
                notebook.pack(fill="both", expand=True)
                owner = SimpleNamespace(
                    tk=tk, ttk=ttk, project=project,
                    project_path=path / "jeu.game.json",
                    project_status=Mock(), _content=lambda: content,
                    _run=lambda callback: callback())
                studio = AudioStudio(owner, notebook)
                studio.asset_id.set("village")
                with patch("tkinter.filedialog.askopenfilename",
                           return_value=str(source)):
                    studio.import_file()
                self.assertIn("village", studio.entry_ids)
                studio.asset.set("village")
                studio.category.set("Musique")
                studio.slot.set("title")
                studio.bind()
                self.assertEqual(
                    owner.project.asset_registry().binding("sound", "title")["id"],
                    "village")
                studio.diagnose()
                self.assertIn("valides", studio.message.get())
                owner.project.save(owner.project_path, content)
                self.assertTrue(owner.project_path.is_file())
                studio.unbind()
                studio.asset_list.selection_set(0)
                studio.remove()
                self.assertEqual(studio.entry_ids, [])
                self.assertTrue((path / "assets/audio/village.wav").is_file())
                studio.stop()
            finally:
                root.destroy()


if __name__ == "__main__":
    unittest.main()
