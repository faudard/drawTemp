"""3.7.21B Tk/Xvfb smoke: undo across map/project, then Save All."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch
from sporebound.model import Content
from sporebound.game_project import GameProject
from sporebound.studio_transaction import StudioTransactionStore


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Run under Tk/Xvfb")
class StudioHistoryGuiTests(unittest.TestCase):
    def test_interrupted_project_write_can_resume_at_startup(self):
        import tkinter as tk
        with TemporaryDirectory() as directory:
            content_path = Path(directory) / "jeanne.json"
            original = Content.load(DEFAULT_CONTENT).to_dict()
            project = GameProject.default(Content.load(DEFAULT_CONTENT)).to_dict()
            store = StudioTransactionStore(content_path)
            store.save(original, project)
            updated = json.loads(json.dumps(original))
            updated["missions"][0]["name"] += " — recovered"
            updated_project = dict(project)
            updated_project["title"] = "Jeanne — sauvegarde retrouvée"
            real_publish = store._publish_one
            counter = []
            def fail_second(path):
                counter.append(path)
                if len(counter) == 2:
                    raise OSError("interrupted")
                real_publish(path)
            with patch.object(store, "_publish_one", side_effect=fail_second):
                with self.assertRaises(OSError):
                    store.save(updated, updated_project)
            self.assertTrue(store.pending)

            def drive(root):
                try:
                    root.update()
                    self.assertFalse(store.pending)
                    self.assertEqual(json.loads(store.content_path.read_text(
                        encoding="utf-8"))["missions"][0]["name"],
                        updated["missions"][0]["name"])
                    self.assertEqual(json.loads(store.project_path.read_text(
                        encoding="utf-8"))["title"], updated_project["title"])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.messagebox.askyesnocancel", return_value=True) as prompt, \
                 patch("tkinter.messagebox.showerror") as show_error:
                launch(content_path)
                prompt.assert_called_once()
                show_error.assert_not_called()

    def test_global_undo_redo_then_save_both_documents(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as directory:
            content_path = Path(directory) / "jeanne.json"
            content_path.write_bytes(Path(DEFAULT_CONTENT).read_bytes())
            project_path = content_path.with_suffix(".game.json")
            callback_errors = []

            def drive(root):
                try:
                    root.report_callback_exception = (
                        lambda *exc: callback_errors.append(exc))
                    root.update()
                    widgets = list(descendants(root))
                    buttons = {w.cget("text"): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    label = next(w for w in widgets if isinstance(w, ttk.Label)
                                 and w.cget("text") == "Titre")
                    title_entry = label.master.grid_slaves(row=0, column=1)[0]
                    previous_title = title_entry.get()

                    # File actions moved from the old button row into
                    # the Studio's real "Fichier" menu. Exercise that UI.
                    file_button = next(
                        w for w in widgets if isinstance(w, ttk.Menubutton)
                        and w.cget("text") == "Fichier ▾")
                    file_menu = root.nametowidget(file_button.cget("menu"))
                    entries = {
                        file_menu.entrycget(i, "label"): i
                        for i in range(file_menu.index("end") + 1)
                        if file_menu.type(i) == "command"
                    }
                    self.assertIn("Nouvelle mission", entries)
                    file_menu.invoke(entries["Nouvelle mission"])
                    root.update()
                    title_entry.delete(0, "end")
                    title_entry.insert(0, "Jeanne — Studio 3.7.21B")
                    buttons["Appliquer configuration"].invoke()
                    root.update()

                    buttons["Annuler"].invoke()  # Undo project, keep new mission.
                    root.update()
                    self.assertEqual(title_entry.get(), previous_title)
                    buttons["Annuler"].invoke()  # Undo mission.
                    root.update()
                    buttons["Enregistrer tout"].invoke()
                    root.update()
                    previous_content = json.loads(content_path.read_text(encoding="utf-8"))
                    self.assertNotIn("history_gate",
                                     [m["id"] for m in previous_content["missions"]])
                    self.assertEqual(json.loads(project_path.read_text(
                        encoding="utf-8"))["title"], previous_title)

                    buttons["Rétablir"].invoke()
                    buttons["Rétablir"].invoke()
                    root.update()
                    buttons["Enregistrer tout"].invoke()
                    root.update()
                    authored = json.loads(content_path.read_text(encoding="utf-8"))
                    self.assertIn("history_gate",
                                  [m["id"] for m in authored["missions"]])
                    saved_project = json.loads(project_path.read_text(encoding="utf-8"))
                    self.assertEqual(saved_project["title"], "Jeanne — Studio 3.7.21B")
                    self.assertFalse(list(Path(directory).glob(
                        "*.studio-recovery.json")))
                    self.assertEqual(callback_errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.simpledialog.askstring", return_value="history_gate"), \
                 patch("tkinter.messagebox.showerror") as show_error:
                launch(content_path)
                show_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
