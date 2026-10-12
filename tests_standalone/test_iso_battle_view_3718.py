"""3.7.18A shared editor/Player isometric projection, no Battle mutations."""
from dataclasses import replace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.iso_battle_view import (
    IsoBattleCanvas, anchored_iso_zoom, battle_layers, hit_test_battle,
    viewport_shift)
from sporebound.iso_map import IsoGeometry
from sporebound.model import Content
from sporebound.presentation import Camera, battle_frame


class FakeCanvas:
    def __init__(self):
        self.items = []

    def winfo_width(self):
        return 820

    def winfo_height(self):
        return 560

    def __getattr__(self, name):
        if name.startswith(('create_', 'tag_', 'move', 'delete', 'configure')):
            def record(*args, **kwargs):
                self.items.append((name, args, kwargs))
                return len(self.items)
            return record
        raise AttributeError(name)

    def tagged(self, tag):
        return [entry for entry in self.items
                if tag in entry[2].get('tags', ())]


class IsoBattleViewTests(unittest.TestCase):
    def setUp(self):
        self.battle = Battle(Content.load(DEFAULT_CONTENT), 'garden', seed=9)
        self.camera = Camera(52, 12, -17)

    def test_2d_isometric_conversion_and_anchored_zoom_at_elevations(self):
        board = self.battle.board
        viewport = (820, 560)
        for size in (24, 52, 96):
            camera = Camera(size, 12, -17)
            geometry = IsoGeometry(board, size)
            shift = viewport_shift(geometry, camera, viewport)
            for cell in ((0, 0), (2, 2), (board.width-1, board.height-1)):
                px, py = geometry.center(cell)
                screen = (px + shift[0], py + shift[1])
                self.assertEqual(hit_test_battle(board, camera, viewport,
                                                 screen), cell)
            self.assertIsNone(hit_test_battle(
                board, camera, viewport, (-10000, -10000)))
        geo = IsoGeometry(board, self.camera.cell_size)
        shift = viewport_shift(geo, self.camera, viewport)
        point = geo.center((2, 2))
        point = (point[0]+shift[0], point[1]+shift[1])
        zoom = anchored_iso_zoom(board, self.camera, viewport, 2, point)
        self.assertEqual(zoom.cell_size, 68)
        shifted = viewport_shift(IsoGeometry(board, 68), zoom, viewport)
        next_point = IsoGeometry(board, 68).center((2, 2))
        self.assertAlmostEqual(next_point[0]+shifted[0], point[0])
        self.assertAlmostEqual(next_point[1]+shifted[1], point[1])
        self.assertEqual(hit_test_battle(board, zoom, viewport, point), (2, 2))
        self.assertEqual(anchored_iso_zoom(board, Camera(128, 0, 0),
                                          viewport, 1, point).cell_size, 128)

    def test_same_battle_state_rendered_with_live_reachable_and_danger(self):
        before = self.battle.digest()
        frame = battle_frame(self.battle, (2, 2))
        frame = replace(frame, danger=(
            {'cell': [3, 3], 'kind': 'cast'},
            {'cell': [3, 3], 'kind': 'hazard'},
            {'cell': [4, 2], 'kind': 'charge'}),
            reachable=((2, 3),), active_id=self.battle.active_id)
        canvas = FakeCanvas()
        renderer = IsoBattleCanvas(canvas)
        # FakeCanvas cannot own Tk PhotoImage; test the pure polygon fallback.
        renderer.terrain._unavailable = True
        renderer.props._unavailable = True
        renderer.buildings._unavailable = True
        renderer.fortifications._unavailable = True
        geo = renderer.draw(self.battle, frame, self.camera)
        self.assertIsInstance(geo, IsoGeometry)
        self.assertEqual(self.battle.digest(), before)
        self.assertTrue(canvas.tagged('iso_reachable'))
        self.assertEqual(len(canvas.tagged('iso_danger_cast')), 1)
        self.assertEqual(len(canvas.tagged('iso_danger_charge')), 1)
        self.assertFalse(canvas.tagged('iso_danger_hazard'))
        self.assertTrue(canvas.tagged('iso_actor'))
        self.assertEqual(renderer.hit_test(
            *(v+o for v, o in zip(geo.center((2, 2)), renderer.shift))), (2, 2))
        renderer.dispose()
        self.assertIsNone(renderer.geometry)

    def test_layer_contract_only_exposes_deployment_during_preparation(self):
        self.assertFalse(battle_layers()['Déploiement'])
        self.assertTrue(battle_layers(deploying=True)['Déploiement'])
        self.assertTrue(battle_layers()['Toitures'])
        self.assertTrue(battle_layers()['Bâtiments'])


if __name__ == '__main__':
    unittest.main()
