"""3.7.19A: real Tk isometric sprite, zoom and MotionDirector visual gate."""
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.iso_actor_atlas import IsoActorAtlas
from sporebound.iso_map import render_isometric
from sporebound.model import Content
from sporebound.visual_motion import ActorPose


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Needs a real Tk/Xvfb screen')
class ActorSpriteGUITests(unittest.TestCase):
    def test_player_keeps_actor_item_ids_when_direction_changes_on_cached_frame(self):
        import tkinter as tk
        from sporebound.engine import Battle
        from sporebound.iso_battle_view import IsoBattleCanvas
        from sporebound.presentation import Camera, battle_frame
        root = tk.Tk()
        root.geometry('980x740+0+0')
        canvas = tk.Canvas(root, width=900, height=700)
        canvas.pack(fill='both', expand=True)
        try:
            root.update()
            battle = Battle(Content.load(DEFAULT_CONTENT), 'garden', seed=2)
            frame = battle_frame(battle, (2, 2))
            camera = Camera(54, 0, 0)
            renderer = IsoBattleCanvas(canvas)
            hero = next(u for u in battle.units if u.team == 'player')
            idle = {hero.id: ActorPose(*hero.pos, 'idle', 'south')}
            move = {hero.id: ActorPose(*hero.pos, 'move', 'east')}
            renderer.draw(battle, frame, camera, poses=idle)
            items = [i for i in canvas.find_withtag('iso_actor_unit_0')
                     if canvas.type(i) == 'image']
            self.assertTrue(items)
            image_before = canvas.itemcget(items[0], 'image')
            creations_before = renderer._scene_rebuilds
            renderer.draw(battle, frame, camera, poses=move)
            self.assertEqual(renderer._scene_rebuilds, creations_before)
            self.assertEqual(renderer._actor_only_frames, 1)
            self.assertEqual(
                items, [i for i in canvas.find_withtag('iso_actor_unit_0')
                        if canvas.type(i) == 'image'])
            self.assertNotEqual(image_before, canvas.itemcget(items[0], 'image'))
            renderer.dispose()
            self.assertEqual(renderer._actor_sprite_states, ())
        finally:
            root.destroy()

    def test_zoom_player_enemy_archer_animation_and_missing_png_fallback(self):
        import tkinter as tk
        root = tk.Tk()
        root.geometry('1040x760+0+0')
        canvas = tk.Canvas(root, bg='#e5dcc7', highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        try:
            root.update()
            source = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                       'chibi_showcase', 'Chibi', 10, 10)
            mission = Content.from_dict(source).missions['chibi_showcase']
            actors = (
                SimpleNamespace(id='hero', name='Jeanne', team='player',
                                pos=(2, 4), facing=(0, 1), footprint=(1, 1),
                                hp=40, alive=True),
                SimpleNamespace(id='guard', name='Garde', team='enemy',
                                pos=(6, 4), facing=(-1, 0), footprint=(1, 1),
                                hp=40, alive=True),
                SimpleNamespace(id='archer', name='Archer', team='enemy',
                                pos=(5, 6), facing=(0, -1), weapon='bow',
                                footprint=(1, 1), hp=30, alive=True),
            )
            atlas = IsoActorAtlas(canvas)
            output = os.environ.get('SPOREBOUND_ACTOR_SCREENSHOT_DIR')
            layers = {'Terrain': True, 'Unités': True}
            for size in (24, 54, 96):
                with self.subTest(size=size):
                    geo = render_isometric(
                        canvas, mission.board, mission, actors,
                        cell_size=size, layers=layers,
                        selected_cell=(0, 0), selected_tiles=(),
                        actor_atlas=atlas)
                    items = canvas.find_withtag('iso_actor_sprite')
                    self.assertEqual(len(items), 3)
                    self.assertEqual(len(canvas.find_withtag('iso_actor')), 6)
                    self.assertIsNotNone(atlas._source)
                    self.assertIsNotNone(atlas._jeanne_source)
                    for iid in items:
                        self.assertEqual(canvas.type(iid), 'image')
                        self.assertTrue(canvas.itemcget(iid, 'image'))
                    # Sprite transparent margins still count as image extent:
                    # name labels must not cover the head at any camera zoom.
                    for idx in range(len(actors)):
                        group = canvas.find_withtag('iso_actor_unit_' + str(idx))
                        picture = next(i for i in group if canvas.type(i) == 'image')
                        title = next(i for i in group if canvas.type(i) == 'text')
                        self.assertLessEqual(canvas.bbox(title)[3],
                                             canvas.bbox(picture)[1])
                    self.assertEqual(geo.hit_test(*geo.center((2, 4))),
                                     (2, 4))
                    root.update()
                    if output:
                        from PIL import ImageGrab
                        dest = Path(output)
                        dest.mkdir(parents=True, exist_ok=True)
                        x, y = root.winfo_rootx(), root.winfo_rooty()
                        ImageGrab.grab(bbox=(x, y, x+root.winfo_width(),
                                             y+root.winfo_height()),
                                       xdisplay=os.environ.get('DISPLAY')).save(
                                           dest / f'chibi-{size}.png')

            poses = {'hero': ActorPose(2.5, 4.0, 'move', 'east')}
            render_isometric(canvas, mission.board, mission, actors,
                             cell_size=54, layers=layers,
                             selected_cell=(0, 0), selected_tiles=(),
                             actor_atlas=atlas, poses=poses)
            self.assertIn(('jeanne', 'east', 1, 54), atlas._cache)
            atlas.clear_cache()
            unavailable = IsoActorAtlas(canvas, path=Path('/missing/actors.png'))
            render_isometric(canvas, mission.board, mission, actors,
                             cell_size=54, layers=layers,
                             selected_cell=(0, 0), selected_tiles=(),
                             actor_atlas=unavailable)
            # Independent approved Jeanne asset remains visible if only the
            # new generic chibi atlas is missing. Guard/archer become circles.
            self.assertEqual(len(canvas.find_withtag('iso_actor_sprite')), 1)
            self.assertEqual(len(canvas.find_withtag('iso_actor')), 6)
            entirely_missing = IsoActorAtlas(
                canvas, path=Path('/missing/actors.png'),
                jeanne_path=Path('/missing/jeanne.png'))
            render_isometric(canvas, mission.board, mission, actors,
                             cell_size=54, layers=layers,
                             selected_cell=(0, 0), selected_tiles=(),
                             actor_atlas=entirely_missing)
            self.assertFalse(canvas.find_withtag('iso_actor_sprite'))
            self.assertEqual(len(canvas.find_withtag('iso_actor')), 6)
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
