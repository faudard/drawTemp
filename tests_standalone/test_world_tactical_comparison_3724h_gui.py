"""3.7.24H Tk smoke: contextual Battle Lab linked to world route comparison."""
import json
import os
import time
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
            "Tk/Xvfb display required")
class WorldTacticalComparisonGUITests(TestCase):
    def test_route_variants_to_battle_lab_matrix_without_saving(self):
        import tkinter as tk

        with TemporaryDirectory() as folder:
            source = Path(folder) / "world.json"
            content = Content.load(DEFAULT_CONTENT)
            source.write_text(json.dumps(content.to_dict()), encoding="utf-8")
            project = GameProject.default(content)
            project.world = default_world(content, project.campaigns)
            project.story = {"scenes": [{
                "id": "escort", "title": "Caravane",
                "speaker": "Marchande", "text": "Faut-il aider ?",
                "choices": [
                    {"id": "yes", "label": "Aider",
                     "effects": [{"kind": "set_flag",
                                  "flag": "road_escort", "value": 1}]},
                    {"id": "no", "label": "Refuser"},
                ],
            }]}
            project.world["events"] = [{
                "id": "caravan", "from": "garden", "to": "escape",
                "step": 2, "scene": "escort",
            }]
            project.battle_support = [{
                "mission": "escape", "flag": "road_escort",
                "gte": 1, "potion_bonus": 2,
            }]
            project.save(source.with_suffix(".game.json"), content)
            worlds, errors = [], []
            before_init = WorldMapStudio.__init__

            def capture(instance, *args, **kwargs):
                before_init(instance, *args, **kwargs)
                worlds.append(instance)

            def drive(root):
                try:
                    root.report_callback_exception = lambda *args: errors.append(args)
                    root.update()
                    tab = worlds[0]
                    tab.show()
                    tab.lab_start.set("garden")
                    tab.lab_destination.set("escape")
                    tab.owner._run(tab.start_lab)
                    tab.owner._run(tab.run_lab)
                    tab.owner._run(tab.mark_comparison)
                    tab.owner._run(tab.auto_comparison)
                    self.assertEqual(len(tab.comparison.variants), 2)
                    tab.tactical_mission.set("escape")
                    tab.tactical_seeds.set("2")
                    tab.tactical_limit.set("12")
                    tab.owner._run(tab.start_tactical_comparison)
                    self.assertTrue(tab._tactical_busy)
                    for _ in range(220):
                        root.update()
                        if not tab._tactical_busy:
                            break
                        time.sleep(.03)
                    self.assertFalse(tab._tactical_busy,
                                     "Battle Lab worker/poll never finished")
                    self.assertIsNotNone(tab.tactical_report)
                    self.assertEqual(tab.tactical_report["reference"],
                                     "1. Aider")
                    self.assertEqual(len(tab.tactical_tree.get_children()), 8)
                    rows = [tab.tactical_tree.item(row, "values")
                            for row in tab.tactical_tree.get_children()]
                    self.assertTrue(any(
                        tuple(values) == ("Potions au départ", "5", "3")
                        for values in rows))
                    self.assertEqual(errors, [])
                    self.assertEqual(tab.owner.project.to_dict(),
                                     project.to_dict())
                finally:
                    root.destroy()

            with (patch.object(tk.Tk, "mainloop", drive),
                  patch.object(WorldMapStudio, "__init__", capture),
                  patch("tkinter.messagebox.showerror") as showerror):
                launch(source)
                showerror.assert_not_called()
            self.assertEqual(Content.load(source).to_dict(),
                             content.to_dict())
            self.assertEqual(GameProject.load(source.with_suffix(".game.json"),
                                              content).to_dict(), project.to_dict())
