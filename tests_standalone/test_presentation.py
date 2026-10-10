"""Presentation projections are deterministic and never advance the engine."""
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.model import Content
from sporebound.presentation import Camera, battle_frame, strategy_frame
from sporebound.fronts import MultiFrontSession


class PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)

    def test_camera_round_trip_pan_and_anchor_zoom(self):
        camera = Camera(40, 12, 17)
        cell = (5, 3)
        x, y = camera.cell_to_screen(cell)
        self.assertEqual(camera.screen_to_cell(x + 1, y + 1), cell)
        zoom = camera.zoomed(2, (120, 90))
        self.assertEqual(zoom.screen_to_cell(120, 90),
                         camera.screen_to_cell(120, 90))
        self.assertEqual(camera.panned(10, -3).offset_x, 22)
        with self.assertRaises(ValueError):
            Camera(2)

    def test_battle_view_is_read_only(self):
        battle = Battle(self.content, 'garden', seed=7)
        before = battle.digest()
        frame = battle_frame(battle, (1, 2), 'attack')
        self.assertEqual(frame.width, battle.board.width)
        self.assertEqual(len(frame.tiles), battle.board.width * battle.board.height)
        self.assertEqual(frame.active_id, battle.active_id)
        self.assertEqual(len(frame.actors), len(battle.units))
        self.assertEqual(before, battle.digest())
        self.assertEqual(frame, battle_frame(battle, (1, 2), 'attack'))

    def test_strategy_frame_is_read_only(self):
        first, second = list(self.content.missions)[:2]
        session = MultiFrontSession(self.content, {'east': first, 'west': second},
                                    'east', seed=11)
        before = session.digest()
        frame = strategy_frame(session)
        self.assertEqual(frame.focused, 'east')
        self.assertEqual({f.id for f in frame.fronts}, {'east', 'west'})
        self.assertEqual(before, session.digest())


if __name__ == '__main__':
    unittest.main()
