"""Placement, frozen clocks, atomic rejection and siege replay integration."""
from copy import deepcopy
import unittest

from examples.siege_scenarios import siege_content
from sporebound.ai import choose_command
from sporebound.engine import Battle
from sporebound.model import Content, RuleError


class DeploymentTests(unittest.TestCase):
    def battle(self, mid='castle_relief'):
        return Battle(siege_content(), mid, seed=42)

    def test_placement_freezes_time_and_replays_before_and_after_start(self):
        b = self.battle()
        rng = b.rng.getstate()
        ct = [u.ct for u in b.units]
        for pos in ([0, 2], [2, 6]):
            b.execute(dict(kind='deploy', unit='captain', cell=pos, facing=[1, 0]))
        self.assertEqual(b.tick, 0)
        self.assertIsNone(b.active)
        self.assertEqual(b.fired, [])
        self.assertEqual(b.rng.getstate(), rng)
        self.assertEqual([u.ct for u in b.units], ct)
        self.assertEqual(b.unit('captain').facing, (1, 0))
        self.assertEqual(Battle.replay(b.recording()).digest(), b.digest())
        b.execute(dict(kind='start_battle'))
        self.assertFalse(b.deploying)
        self.assertIsNotNone(b.active)
        self.assertEqual(Battle.replay(b.recording()).digest(), b.digest())
        for _ in range(6):
            b.execute(choose_command(b))
        self.assertEqual(Battle.replay(b.recording()).digest(), b.digest())

    def test_rejections_are_atomic(self):
        b = self.battle()
        commands = [
            dict(kind='move', cell=[0, 2]), dict(kind='end'),
            dict(kind='deploy', unit='defender', cell=[0, 2]),
            dict(kind='deploy', unit='unknown', cell=[0, 2]),
            dict(kind='deploy', unit='captain', cell=[1, 5]),
            dict(kind='deploy', unit='captain', cell=[9, 3]),
            dict(kind='deploy', unit='captain', cell=[True, 3]),
            dict(kind='deploy', unit='captain', cell=[0, 2], facing=[1, 1]),
        ]
        before = deepcopy(b.recording())
        for cmd in commands:
            with self.subTest(command=cmd), self.assertRaises(RuleError):
                b.execute(cmd)
            self.assertEqual(b.recording(), before)
        b.execute(dict(kind='start_battle'))
        before = b.recording()
        with self.assertRaises(RuleError):
            b.execute(dict(kind='deploy', unit='captain', cell=[0, 2]))
        self.assertEqual(b.recording(), before)

    def test_large_player_needs_entire_footprint_in_zone(self):
        content = siege_content()
        content.missions['castle_ram'].units[0].footprint = (2, 2)
        b = Battle(content, 'castle_ram')
        with self.assertRaises(RuleError):
            b.execute(dict(kind='deploy', unit='captain', cell=[2, 2]))
        b.execute(dict(kind='deploy', unit='captain', cell=[0, 2]))
        self.assertEqual(len(b.unit('captain').occupied_cells()), 4)

    def test_invalid_authoring_rejected(self):
        for zones in (None, [{}], [{'id':'x','cells':[]}],
                      [{'id':'x','cells':[[8, 3]]}],
                      [{'id':'x','cells':[[0, 0],[0, 0]]}]):
            data = siege_content().to_dict()
            data['missions'][0]['deployment'] = zones
            with self.subTest(zones=zones), self.assertRaises(RuleError):
                Content.from_dict(data)

    def test_mission_without_deployment_retains_immediate_activation(self):
        content = siege_content()
        content.missions['castle_ram'].deployment = []
        b = Battle(content, 'castle_ram')
        self.assertFalse(b.deploying)
        self.assertIsNotNone(b.active)
        self.assertNotIn('deploying', b.state())

    def test_ai_explicitly_accepts_authored_formation(self):
        b = self.battle()
        before = b.digest()
        self.assertEqual(choose_command(b), {'kind':'start_battle'})
        self.assertEqual(before, b.digest())

    def test_locked_gate_rejects_direct_opening(self):
        b = self.battle()
        b.execute(dict(kind="start_battle"))
        b.unit("captain").pos = (7, 3)
        b.active_id = "captain"
        before = b.digest()
        with self.assertRaises(RuleError):
            b.execute(dict(kind="interact", object="main_gate"))
        self.assertEqual(b.digest(), before)

    def test_ram_must_open_the_only_passage(self):
        b = self.battle('castle_ram')
        b.execute(dict(kind='start_battle'))
        self.assertTrue(all(b.board.tile((8, y)).blocked for y in range(8)))
        # Move the operator along with the ram, then strike repeatedly.
        for _ in range(9):
            ram = next(o for o in b.mission.objects if o['id'] == 'ram')
            u = b.unit('captain')
            u.pos = (ram['pos'][0]-1, ram['pos'][1])
            u.acted = False
            b.active_id = u.id
            b.execute(dict(kind='interact', object='ram'))
            if not b.board.tile((8,3)).blocked:
                break
        self.assertFalse(b.board.tile((8,3)).blocked)
        self.assertTrue(all(b.board.tile((8,y)).blocked for y in range(8) if y != 3))


if __name__ == '__main__':
    unittest.main()
