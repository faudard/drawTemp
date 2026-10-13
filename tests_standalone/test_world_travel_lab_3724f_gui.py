"""3.7.24F Tk integration: sandbox travel, choice, route and no saved mutation."""
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
            "Requires the Tk GUI and Xvfb")
class WorldTravelLabGUITests(TestCase):
    def test_simulate_story_choice_then_undo_save_does_not_commit_lab(self):
        import tkinter as tk

        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "world.json"
            content = Content.load(DEFAULT_CONTENT)
            source.write_text(json.dumps(content.to_dict()), encoding="utf-8")
            project = GameProject.default(content)
            project.world = default_world(content, project.campaigns)
            project.story = {"scenes": [
                {"id": "caravan", "title": "La caravane",
                 "speaker": "Marchande", "text": "Une caravane est attaquée.",
                 "choices": [
                     {"id": "help", "label": "Protéger la caravane",
                      "effects": [{"kind": "set_flag", "flag": "rescued_caravan",
                                   "value": True}]},
                     {"id": "back", "label": "Retourner au village"},
                 ]},
                {"id": "toll", "title": "Péage",
                 "speaker": "Garde", "text": "Arrêtez-vous.",
                 "choices": [{"id": "pass", "label": "Continuer"}]},
            ]}
            project.world["events"] = [
                {"id": "caravan", "from": "garden", "to": "escape",
                 "step": 2, "scene": "caravan",
                 "routes": {"back": {"kind": "return"}}},
                {"id": "toll", "from": "garden", "to": "escape",
                 "step": 6, "scene": "toll"},
            ]
            project.validate(content)
            manifest = source.with_suffix(".game.json")
            project.save(manifest, content)
            worlds, errors = [], []
            init = WorldMapStudio.__init__

            def capture(instance, *args, **kwargs):
                init(instance, *args, **kwargs)
                worlds.append(instance)

            def drive(root):
                try:
                    root.report_callback_exception = lambda *x: errors.append(x)
                    root.update()
                    studio = worlds[0]
                    studio.show()
                    studio.lab_start.set("garden")
                    studio.lab_destination.set("escape")
                    studio.owner._run(studio.start_lab)
                    root.update()
                    self.assertIsNotNone(studio.lab)
                    self.assertEqual(studio.lab.snapshot()["world"]["at"], "garden")
                    studio.owner._run(studio.run_lab)
                    root.update()
                    self.assertEqual(studio.lab.snapshot()["scene"]["id"], "caravan")
                    self.assertEqual(len(studio.canvas.find_withtag(
                        "world_lab_party")), 1)
                    studio.lab_choice.set("help")
                    studio.owner._run(studio.choose_lab)
                    self.assertIn("Flag rescued_caravan",
                                  studio.lab_log.get("1.0", "end"))
                    studio.owner._run(studio.run_lab)
                    self.assertEqual(studio.lab.snapshot()["scene"]["id"], "toll")
                    studio.lab_choice.set("pass")
                    studio.owner._run(studio.choose_lab)
                    studio.owner._run(studio.run_lab)
                    self.assertTrue(studio.lab.snapshot()["finished"])
                    self.assertEqual(studio.lab.snapshot()["world"]["at"], "escape")
                    self.assertEqual(studio.owner.project.to_dict(), project.to_dict())

                    # A Studio content or world modification invalidates the
                    # running sandbox and cannot write its private flags.
                    studio.selected.set("garden")
                    node = next(n for n in project.world["nodes"]
                                if n["mission"] == "garden")
                    studio.region.set("Updated")
                    studio.owner._run(studio.set_region)
                    root.update()
                    self.assertIsNone(studio.lab)
                    self.assertIn("invalidée", studio.lab_status.get())
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with (patch.object(tk.Tk, "mainloop", drive),
                  patch.object(WorldMapStudio, "__init__", capture),
                  patch("tkinter.messagebox.showerror") as popup):
                launch(source)
                popup.assert_not_called()
            self.assertEqual(Content.load(source).to_dict(), content.to_dict())
            # The content/profile files do not change when only the sandbox
            # was used; the map edit above is intentionally not saved.
            self.assertEqual(GameProject.load(manifest, content).to_dict(),
                             project.to_dict())
