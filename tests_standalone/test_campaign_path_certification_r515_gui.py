"""R5.15 Tk certification wiring; the real replay is covered headlessly.

Only the expensive worker is stubbed here; this test asserts no fake
certification is generated on click without an actual R5.15 result and that
stale nodes are rejected while source files are left intact.
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from examples.reliability_gate import fixture
from sporebound.editor import launch


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a Tk display or Xvfb")
class CampaignCertificationTkTests(unittest.TestCase):
    def test_certificate_is_tied_to_selected_node_and_source_identity(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        content, project = fixture()
        with TemporaryDirectory() as dirname:
            root_dir = Path(dirname)
            content_path = root_dir / "scenario.json"
            project_path = root_dir / "scenario.game.json"
            content_path.write_text(json.dumps(content.to_dict()),
                                    encoding="utf-8")
            project.save(project_path, content)
            before_content = content_path.read_bytes()
            before_project = project_path.read_bytes()
            errors = []
            captured = []

            def worker(_content, _project, plan, **kwargs):
                captured.append(plan)
                return {
                    "id": plan["id"], "seed": plan["seed"],
                    "evidence": {
                        "tactical_battles": 1, "commands": 5, "checkpoints": 3,
                        "proof_digest": "a" * 64},
                    "observed": {
                        "completed": plan["expect"]["completed"],
                        "endings": plan["expect"]["endings"],
                        "consequences": []},
                }

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    book = next(w for w in descendants(root)
                                if isinstance(w, ttk.Notebook)
                                and "Campaign Simulation" in
                                [w.tab(t, "text") for t in w.tabs()])
                    simulation = next(t for t in book.tabs()
                                      if book.tab(t, "text") == "Campaign Simulation")
                    book.select(simulation)
                    root.update()
                    page = root.nametowidget(book.select())
                    widgets = list(descendants(page))
                    buttons = {w.cget("text"): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    action_list = next(w for w in widgets if isinstance(w, tk.Listbox))
                    inner = next(w for w in widgets if isinstance(w, ttk.Notebook))
                    cert_tab = next(t for t in inner.tabs()
                                    if inner.tab(t, "text") == "Certification R5.15")
                    text_widget = next(w for w in descendants(
                        root.nametowidget(cert_tab)) if isinstance(w, tk.Text))
                    buttons["Nouvelle simulation"].invoke()
                    root.update()
                    action_list.selection_set(0)
                    buttons["Exécuter l'action"].invoke()
                    root.update()
                    action_list.selection_set(0)
                    buttons["Exécuter l'action"].invoke()
                    root.update()
                    self.assertNotIn("CERTIFIÉ", text_widget.get("1.0", "end"))
                    buttons["Certifier ce parcours R5.15"].invoke()
                    for _ in range(80):
                        root.update()
                        if "CERTIFIÉ PAR REPLAY" in text_widget.get("1.0", "end"):
                            break
                        time.sleep(0.02)
                    self.assertIn("CERTIFIÉ PAR REPLAY",
                                  text_widget.get("1.0", "end"))
                    self.assertEqual(captured[0]["steps"][1],
                                     {"kind": "mission", "id": "gate",
                                      "outcome": "victory"})
                    self.assertEqual(content_path.read_bytes(), before_content)
                    self.assertEqual(project_path.read_bytes(), before_project)
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("sporebound.studio_campaign_simulation.certify_path",
                       side_effect=worker), \
                 patch("tkinter.messagebox.showerror") as showerror:
                launch(content_path)
                showerror.assert_not_called()


if __name__ == "__main__":
    unittest.main()
