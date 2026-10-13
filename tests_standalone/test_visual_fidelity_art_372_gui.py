"""Tk/Xvfb Editor vs Player parity: same atlas, zoom, layers and occlusion."""
import os
from pathlib import Path
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor_render_cache import EditorRenderCache
from sporebound.engine import Battle
from sporebound.iso_actor_atlas import IsoActorAtlas
from sporebound.iso_battle_view import IsoBattleCanvas, battle_layers
from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_fortification_atlas import IsoFortificationAtlas
from sporebound.iso_map import IsoTerrainAtlas
from sporebound.iso_object_atlas import IsoObjectAtlas
from sporebound.iso_props import IsoPropAtlas
from sporebound.iso_structures import place_structure
from sporebound.model import Content
from sporebound.presentation import Camera, battle_frame
from sporebound.visual_motion import ActorPose


def signature(canvas, *, shift=(0, 0)):
    """Compare actual Canvas stacking, anchor positions and sprite pixels.

    Each Canvas owns distinct Tk PhotoImage names, so image identity is
    normalized to dimensions, a sample pixel and alpha visibility.
    """
    result = []
    for item in canvas.find_all():
        kind = canvas.type(item)
        coords = canvas.coords(item)
        local = tuple(round(v - shift[index % 2], 2)
                      for index, v in enumerate(coords))
        # Tk automatically adds 'current' to the pointer-hovered item.
        # It is ephemeral UI state, not a source scene/compositing difference.
        tags = tuple(tag for tag in canvas.gettags(item) if tag != 'current')
        if kind == 'image':
            image = canvas.itemcget(item, 'image')
            width = int(canvas.tk.call('image', 'width', image))
            height = int(canvas.tk.call('image', 'height', image))
            sx, sy = max(0, width // 2), max(0, height // 2)
            sample = tuple(canvas.tk.call(image, 'get', sx, sy))
            alpha = str(canvas.tk.call(image, 'transparency', 'get', 0, 0))
            style = (width, height, sample, alpha,
                     canvas.itemcget(item, 'anchor'))
        elif kind == 'text':
            style = (canvas.itemcget(item, 'text'),
                     canvas.itemcget(item, 'fill'))
        else:
            style = (canvas.itemcget(item, 'fill'),)
        result.append((kind, local, tags, style))
    return tuple(result)


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Real Tk/Xvfb screen required')
class VisualFidelityParityGuiTests(unittest.TestCase):
    def test_editor_player_match_at_three_zooms_with_roofs_and_fractional_pose(self):
        import tkinter as tk
        root = tk.Tk()
        root.geometry('1810x800+0+0')
        editor_canvas = tk.Canvas(root, width=880, height=740, highlightthickness=0)
        player_canvas = tk.Canvas(root, width=880, height=740, highlightthickness=0)
        editor_canvas.pack(side='left')
        player_canvas.pack(side='left')
        try:
            root.update()
            data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                     'art_parity', 'Art parity', 12, 12)
            data = place_structure(data, 'art_parity', 'Maison', (3, 3))
            row = next(m for m in data['missions'] if m['id'] == 'art_parity')
            # The rear actor stands immediately beside the footprint: its
            # upper sprite overlaps the house before the doorway cutaway.
            row['units'][0]['pos'] = [2, 4]
            row['units'][1]['pos'] = [9, 9]
            row['board']['tiles'].append({'pos': [9, 7], 'feature': 'tree'})
            row['objects'] = [{'id': 'chest_1', 'kind': 'chest', 'pos': [9, 8]}]
            battle = Battle(Content.from_dict(data), 'art_parity', seed=7)
            digest = battle.digest()
            frame = battle_frame(battle, (0, 0))
            editor = EditorRenderCache(editor_canvas)
            player = IsoBattleCanvas(player_canvas)
            atlases = dict(
                atlas=IsoTerrainAtlas(editor_canvas),
                prop_atlas=IsoPropAtlas(editor_canvas),
                object_atlas=IsoObjectAtlas(editor_canvas),
                building_atlas=IsoBuildingAtlas(editor_canvas),
                fortification_atlas=IsoFortificationAtlas(editor_canvas),
                actor_atlas=IsoActorAtlas(editor_canvas))
            for zoom in (24, 54, 96):
                for state, poses in (
                    ('outside', None),
                    ('cutaway', {battle.units[0].id: ActorPose(
                        2.4, 4.0, 'move', 'east')})):
                    with self.subTest(zoom=zoom, state=state):
                        options = dict(
                            cell_size=zoom,
                            layers=battle_layers(deploying=battle.deploying),
                            selected_cell=frame.selected, selected_tiles=(),
                            reachable=frame.reachable, danger=frame.danger,
                            active_id=frame.active_id, poses=poses)
                        editor.draw(battle.board, battle.mission, battle.units,
                                    **options, **atlases)
                        player.draw(battle, frame, Camera(zoom, 0, 0),
                                    poses=poses)
                        root.update()
                        self.assertEqual(
                            signature(editor_canvas),
                            signature(player_canvas, shift=player.shift))
                        # Compare actual occlusion, not only Editor/Player parity:
                        # rear actor < façade < foreground actor on Canvas.
                        if state == 'outside':
                            stack = {item: idx for idx, item in
                                     enumerate(editor_canvas.find_all())}
                            rear = editor_canvas.find_withtag('iso_actor_unit_0')
                            wall = editor_canvas.find_withtag('architecture_instance_0')
                            front = editor_canvas.find_withtag('iso_actor_unit_1')
                            self.assertTrue(rear and wall and front)
                            self.assertLess(max(stack[i] for i in rear),
                                            min(stack[i] for i in wall))
                            self.assertLess(max(stack[i] for i in wall),
                                            min(stack[i] for i in front))
                        for canvas in (editor_canvas, player_canvas):
                            for item in canvas.find_withtag('iso_actor_sprite'):
                                self.assertEqual(canvas.itemcget(item, 'anchor'), 's')
                        self.assertEqual(bool(editor_canvas.find_withtag(
                            'architecture_sprite')), state == 'outside')
                        self.assertEqual(bool(player_canvas.find_withtag(
                            'architecture_sprite')), state == 'outside')
                        for tag in ('iso_actor_sprite', 'iso_object_sprite',
                                    'decor_sprite'):
                            self.assertTrue(editor_canvas.find_withtag(tag), tag)
                            self.assertEqual(
                                len(editor_canvas.find_withtag(tag)),
                                len(player_canvas.find_withtag(tag)))
                        if os.environ.get('SPOREBOUND_FIDELITY_SCREENSHOT_DIR'):
                            from PIL import ImageGrab
                            output = Path(os.environ['SPOREBOUND_FIDELITY_SCREENSHOT_DIR'])
                            output.mkdir(parents=True, exist_ok=True)
                            for label, canvas in [('editor', editor_canvas),
                                                  ('player', player_canvas)]:
                                x, y = canvas.winfo_rootx(), canvas.winfo_rooty()
                                ImageGrab.grab(bbox=(
                                    x, y, x + canvas.winfo_width(),
                                    y + canvas.winfo_height()),
                                    xdisplay=os.environ.get('DISPLAY')).save(
                                        output / f'{label}-{zoom}-{state}.png')
            self.assertEqual(battle.digest(), digest)
            player.dispose()
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
