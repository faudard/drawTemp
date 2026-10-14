"""3.7.24G Tk/Xvfb smoke: compare forks in World Studio, never save them."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.studio_world_map import WorldMapStudio
from sporebound.world_map import default_world


@skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
            "Requires a display (Xvfb on CI)")
class CompareWorldJourneysGUITests(TestCase):
    def test_auto_then_manual_variants_table_and_editor_invalidation(self):
        import tkinter as tk

        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "world.json"
            content = Content.load(DEFAULT_CONTENT)
            content.missions["garden"].next_missions.append("hold")
            original_content = content.to_dict()
            source.write_text(json.dumps(original_content), encoding="utf-8")
            project = GameProject.default(content)
            project.world = default_world(content, project.campaigns)
            project.story = {"scenes": [
                {"id": "caravan", "title": "Caravane", "speaker": "Marchande",
                 "text": "Choisissez la route.", "choices": [
                     {"id": "forward", "label": "Protéger la caravane",
                      "effects": [{"kind": "set_flag", "flag": "friend",
                                   "value": True}]},
                     {"id": "back", "label": "Faire demi-tour"},
                     {"id": "north", "label": "Vers les collines",
                      "effects": [{"kind": "unlock_mission",
                                   "mission": "hold"}]},
                 ]},
                {"id": "toll", "title": "Péage", "speaker": "Garde",
                 "text": "Vous devez payer.", "choices": [
                     {"id": "pass", "label": "Continuer"},
                 ]},
            ]}
            project.world["events"] = [
                {"id": "caravan", "from": "garden", "to": "escape",
                 "scene": "caravan", "step": 2,
                 "routes": {"back": {"kind": "return"},
                            "north": {"kind": "destination", "mission": "hold"}}},
                {"id": "toll", "from": "garden", "to": "escape",
                 "scene": "toll", "step": 6},
            ]
            project.save(source.with_suffix(".game.json"), content)
            tabs, errors = [], []
            before_init = WorldMapStudio.__init__

            def capture(instance, *a, **kw):
                before_init(instance, *a, **kw)
                tabs.append(instance)

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    tab = tabs[0]
                    tab.show()
                    tab.lab_start.set("garden")
                    tab.lab_destination.set("escape")
                    tab.owner._run(tab.start_lab)
                    tab.owner._run(tab.run_lab)
                    self.assertEqual(tab.lab.snapshot()["scene"]["id"], "caravan")
                    tab.owner._run(tab.mark_comparison)
                    root.update()
                    self.assertIsNotNone(tab.comparison)
                    self.assertTrue(tab.comparison_selected.get() == "")
                    tab.owner._run(tab.auto_comparison)
                    root.update()
                    matrix = tab.comparison.matrix()
                    self.assertEqual(len(matrix["names"]), 3)
                    self.assertEqual(
                        len(tab.comparison_tree["columns"]), 4)
                    self.assertTrue(any(
                        row["metric"] == "Accessible : hold" and
                        row["values"] == ["non", "non", "oui"]
                        for row in matrix["rows"]))
                    chosen = matrix["names"][2]
                    tab.comparison_selected.set(chosen)
                    tab.owner._run(tab.load_comparison)
                    self.assertEqual(tab.lab.snapshot()["world"]["at"], "hold")
                    tab.owner._run(tab.restore_comparison)
                    self.assertEqual(tab.lab.snapshot()["scene"]["id"], "caravan")
                    tab.lab_choice.set("forward")
                    tab.owner._run(tab.choose_lab)
                    tab.owner._run(tab.run_lab)
                    self.assertEqual(tab.lab.snapshot()["scene"]["id"], "toll")
                    tab.lab_choice.set("pass")
                    tab.owner._run(tab.choose_lab)
                    tab.owner._run(tab.run_lab)
                    tab.comparison_name.set("Route complète")
                    tab.owner._run(tab.save_comparison)
                    self.assertEqual(len(tab.comparison.variants), 4)
                    self.assertEqual(tab.comparison.detail(
                        "Route complète")["state"]["at"], "escape")
                    self.assertEqual(tab.owner.project.to_dict(),
                                     project.to_dict())
                    tab.selected.set("garden")
                    tab.region.set("Nouvelle région")
                    tab.owner._run(tab.set_region)
                    root.update()
                    self.assertIsNone(tab.comparison)
                    self.assertIsNone(tab.lab)
                    self.assertFalse(errors)
                finally:
                    root.destroy()

            with (patch.object(tk.Tk, "mainloop", drive),
                  patch.object(WorldMapStudio, "__init__", capture),
                  patch("tkinter.messagebox.showerror") as popup):
                launch(source)
                popup.assert_not_called()
            self.assertEqual(Content.load(source).to_dict(), original_content)
            self.assertEqual(GameProject.load(source.with_suffix(".game.json"),
                                               content).to_dict(),
                             project.to_dict())
