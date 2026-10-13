"""3.7.24E visual Studio gate using actual Tk, StudioHistory and Save All."""
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
class WorldEventStudioGUITests(TestCase):
    def test_select_route_create_two_events_branches_undo_redo_save(self):
        import tkinter as tk
        from tkinter import ttk

        with TemporaryDirectory() as folder:
            source = Path(folder) / "world_content.json"
            content = Content.load(DEFAULT_CONTENT)
            original_content = content.to_dict()
            source.write_text(json.dumps(original_content), encoding="utf-8")
            project = GameProject.default(content)
            project.world = default_world(content, project.campaigns)
            project.story = {"scenes": [{
                "id": "road_choices", "title": "Caravane en danger",
                "speaker": "Voyageur", "text": "La route se divise.",
                "choices": [
                    {"id": "fight", "label": "Se battre"},
                    {"id": "back", "label": "Faire demi-tour"},
                ],
            }]}
            project.save(source.with_suffix(".game.json"), content)
            world_tabs, errors = [], []
            original_init = WorldMapStudio.__init__

            def capture(instance, *args, **kwargs):
                original_init(instance, *args, **kwargs)
                world_tabs.append(instance)

            def descendants(parent):
                for child in parent.winfo_children():
                    yield child
                    yield from descendants(child)

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    tab = world_tabs[0]
                    tab.show()
                    root.update()
                    start = project.campaigns[0]["start_mission"]
                    end = content.missions[start].next_missions[0]
                    nodes = {n["mission"]: n for n in project.world["nodes"]}
                    x = (nodes[start]["x"] + nodes[end]["x"]) // 2
                    y = (nodes[start]["y"] + nodes[end]["y"]) // 2
                    tab.canvas.event_generate("<Button-1>", x=x, y=y)
                    root.update()
                    self.assertEqual(tab.road, (start, end))
                    tab.event_id.set("ambush")
                    tab.event_scene.set("road_choices")
                    tab.event_step.set("2")
                    tab.owner._run(tab.save_event)
                    root.update()
                    self.assertEqual(len(tab.owner.project.world["events"]), 1)
                    tab.event_choice.set("back")
                    tab.event_action.set("return")
                    tab.owner._run(tab.save_choice)
                    root.update()
                    self.assertEqual(
                        tab.owner.project.world["events"][0]["routes"]["back"],
                        {"kind": "return"})
                    tab.owner._run(tab.preview_event)
                    self.assertIn("revenir au carrefour",
                                  tab.event_preview.get("1.0", "end"))

                    tab.new_event()
                    tab.event_id.set("road_toll")
                    tab.event_scene.set("road_choices")
                    tab.event_step.set("6")
                    tab.owner._run(tab.save_event)
                    root.update()
                    self.assertEqual(tab.event_list.size(), 2)
                    self.assertEqual(
                        len(tab.canvas.find_withtag("world_road_event")), 4)

                    buttons = {b.cget("text"): b for b in descendants(root)
                               if isinstance(b, ttk.Button)}
                    buttons["Annuler"].invoke()
                    root.update()
                    self.assertEqual(len(tab.owner.project.world["events"]), 1)
                    buttons["Rétablir"].invoke()
                    root.update()
                    self.assertEqual(len(tab.owner.project.world["events"]), 2)
                    buttons["Enregistrer tout"].invoke()
                    root.update()
                    saved = GameProject.load(
                        source.with_suffix(".game.json"), Content.load(source))
                    self.assertEqual(saved.world,
                                     tab.owner.project.world)
                    self.assertEqual(saved.story, project.story)
                    self.assertEqual(Content.load(source).to_dict(),
                                     original_content)
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with (patch.object(tk.Tk, "mainloop", drive),
                  patch.object(WorldMapStudio, "__init__", capture),
                  patch("tkinter.messagebox.showerror") as popup):
                launch(source)
                popup.assert_not_called()
