"""World Map Studio end-to-end Tk smoke with real shared history/save."""
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
from sporebound.world_map_view import draw_world_map
from sporebound.world_map import world_projection


@skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
            "Requires real Tk/Xvfb display")
class WorldMapGUITests(TestCase):
    def test_world_drag_save_history_and_renderer_parity(self):
        import tkinter as tk
        from tkinter import ttk

        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "world_content.json"
            source.write_text(json.dumps(Content.load(DEFAULT_CONTENT).to_dict()),
                              encoding="utf-8")
            original_content = json.loads(source.read_text(encoding="utf-8"))
            worlds, errors = [], []
            original_init = WorldMapStudio.__init__

            def capture(instance, *args, **kwargs):
                original_init(instance, *args, **kwargs)
                worlds.append(instance)

            def descendants(parent):
                for child in parent.winfo_children():
                    yield child
                    yield from descendants(child)

            def drive(root):
                try:
                    root.report_callback_exception = lambda *items: errors.append(items)
                    root.update()
                    studio_world = worlds[0]
                    studio_world.show()
                    root.update()
                    buttons = {w.cget("text"): w for w in descendants(root)
                               if isinstance(w, ttk.Button)}
                    buttons["Créer la carte du monde"].invoke()
                    root.update()
                    project = studio_world.owner.project
                    self.assertTrue(project.world)
                    mid = project.world["nodes"][0]["mission"]
                    original = next(n for n in project.world["nodes"]
                                    if n["mission"] == mid)
                    old_xy = original["x"], original["y"]
                    canvas = studio_world.canvas
                    projection = world_projection(project.world,
                                                  studio_world.owner._content())
                    self.assertEqual(len(canvas.find_withtag("world_node")),
                                     len(projection["nodes"]) * 2)
                    px, py = old_xy
                    canvas.event_generate("<Button-1>", x=px, y=py)
                    canvas.event_generate("<B1-Motion>", x=px+36, y=py+22)
                    canvas.event_generate("<ButtonRelease-1>", x=px+36, y=py+22)
                    root.update()
                    moved = next(n for n in studio_world.owner.project.world["nodes"]
                                 if n["mission"] == mid)
                    self.assertEqual((moved["x"], moved["y"]),
                                     (px+36, py+22))
                    buttons["Annuler"].invoke()
                    root.update()
                    undone = next(n for n in studio_world.owner.project.world["nodes"]
                                  if n["mission"] == mid)
                    self.assertEqual((undone["x"], undone["y"]), old_xy)
                    buttons["Rétablir"].invoke()
                    root.update()
                    redone = next(n for n in studio_world.owner.project.world["nodes"]
                                  if n["mission"] == mid)
                    self.assertEqual((redone["x"], redone["y"]), (px+36, py+22))
                    buttons["Enregistrer tout"].invoke()
                    root.update()
                    content = Content.load(source)
                    reloaded = GameProject.load(source.with_suffix(".game.json"),
                                                content)
                    self.assertEqual(reloaded.world,
                                     studio_world.owner.project.world)
                    self.assertEqual(content.to_dict(), original_content)
                    # Same graphical projection is used by the Player.
                    player_canvas = tk.Canvas(root, width=900, height=520)
                    player_canvas.pack()
                    player_projection = world_projection(
                        reloaded.world, content, available=[mid])
                    self.assertEqual(draw_world_map(player_canvas,
                                                    player_projection),
                                     len(player_projection["nodes"]))
                    self.assertEqual(len(player_canvas.find_withtag("world_node")),
                                     len(player_projection["nodes"]) * 2)
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with (patch.object(tk.Tk, "mainloop", drive),
                  patch.object(WorldMapStudio, "__init__", capture),
                  patch("tkinter.messagebox.showerror") as error):
                launch(source)
                error.assert_not_called()

    def test_player_world_refuses_locked_marker_and_opens_real_mission(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.player_app import PlayerApplication, launch as launch_player
        from sporebound.world_map import default_world
        from sporebound.game_session import GameSession

        with TemporaryDirectory() as folder:
            source = Path(folder) / "player_content.json"
            content = Content.load(DEFAULT_CONTENT)
            source.write_text(json.dumps(content.to_dict()), encoding="utf-8")
            base = GameProject.default(content)
            world = default_world(content, base.campaigns)
            project = GameProject.from_dict(
                {**base.to_dict(), "world": world}, content)
            project.save(source.with_suffix(".game.json"), content)
            preview_session = GameSession.new(content, project, "main")
            projection = world_projection(
                world, content, available=preview_session.available_missions())
            locked = next((node for node in projection["nodes"]
                           if node["status"] == "locked"), None)
            available = next(node for node in projection["nodes"]
                             if node["status"] == "available")
            sessions, errors = [], []
            original_init = PlayerApplication.__init__

            def capture(instance, *args, **kwargs):
                original_init(instance, *args, **kwargs)
                sessions.append(instance)

            def descendants(parent):
                for child in parent.winfo_children():
                    yield child
                    yield from descendants(child)

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)

                    def button(label):
                        return next(w for w in descendants(root)
                                    if isinstance(w, ttk.Button)
                                    and w.cget("text") == label)

                    root.update()
                    button("Nouvelle partie").invoke()
                    root.update()
                    button("Carte du monde").invoke()
                    root.update()
                    self.assertEqual(sessions[0].player.session.mode, "campaign")
                    map_canvas = next(w for w in descendants(root)
                                      if isinstance(w, tk.Canvas)
                                      and w.find_withtag("world_node"))
                    if locked is not None:
                        map_canvas.event_generate(
                            "<Button-1>", x=locked["x"], y=locked["y"])
                        root.update()
                        self.assertEqual(sessions[0].player.session.mode,
                                         "campaign")
                    map_canvas.event_generate(
                        "<Button-1>", x=available["x"], y=available["y"])
                    root.update()
                    self.assertEqual(sessions[0].player.session.mode, "battle")
                    self.assertEqual(
                        sessions[0].player.session.active_battle.mission.id,
                        available["mission"])
                    self.assertFalse(errors)
                finally:
                    root.destroy()

            with (patch.object(tk.Tk, "mainloop", drive),
                  patch.object(PlayerApplication, "__init__", capture),
                  patch("tkinter.messagebox.showerror") as error):
                launch_player(
                    source, project_path=source.with_suffix(".game.json"),
                    profile_path=Path(folder) / "profile.json")
                error.assert_not_called()
