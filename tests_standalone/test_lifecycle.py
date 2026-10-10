"""Regression tests for actor lifecycle service."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sporebound.lifecycle import spawn, despawn
from sporebound.engine import Battle


class LifecycleTests(unittest.TestCase):
    def make_battle(self):
        from sporebound.model import Board
        return SimpleNamespace(
            content=SimpleNamespace(archetypes={}, skills={}),
            rules=SimpleNamespace(), board=Board(5, 5), units=[],
            mission=SimpleNamespace(protected_id=''), prepared_reactions={},
            carrier=None, relic_pos=None, active_id=None, events=[],
            emit=lambda *args, **kwargs: None, _collect=lambda actor: None,
        )

    def test_spawn_and_despawn(self):
        battle = self.make_battle()
        with patch('sporebound.lifecycle.validate_actor'):
            actor = spawn(battle, {'id': 'wolf_1', 'name': 'Wolf', 'team': 'enemy',
                                   'pos': [2, 2], 'kind': 'monster'})
            self.assertEqual(actor.id, 'wolf_1')
            self.assertEqual(len(battle.units), 1)
            with self.assertRaises(Exception):
                spawn(battle, {'id': 'wolf_1', 'name': 'Wolf', 'team': 'enemy', 'pos': [3, 2]})
            with self.assertRaises(Exception):
                spawn(battle, {'id': 'wolf_2', 'name': 'Wolf', 'team': 'enemy', 'pos': [2, 2]})
            battle.prepared_reactions['wolf_1'] = {'kind': 'guard'}
            despawn(battle, 'wolf_1')
            self.assertEqual(battle.units, [])
            self.assertNotIn('wolf_1', battle.prepared_reactions)

    def test_protected_actor_cannot_despawn(self):
        battle = self.make_battle()
        with patch('sporebound.lifecycle.validate_actor'):
            spawn(battle, {'id': 'hero', 'name': 'Hero', 'team': 'player', 'pos': [1, 1]})
        battle.mission.protected_id = 'hero'
        with self.assertRaises(Exception):
            despawn(battle, 'hero')
        self.assertEqual(len(battle.units), 1)

    def test_wave_rolls_back_after_partial_spawn(self):
        from copy import deepcopy
        source = self.make_battle()
        source.lifetimes = {}
        source.summon_owners = {}
        source.tick = 4

        class WaveBattle(Battle):
            def __init__(self, original):
                self.__dict__.update(deepcopy(original.__dict__))

        battle = WaveBattle(source)
        with patch('sporebound.lifecycle.validate_actor'):
            with self.assertRaises(Exception):
                battle.spawn_wave([
                    {'id': 'a', 'name': 'A', 'team': 'enemy', 'pos': [1, 1]},
                    {'id': 'b', 'name': 'B', 'team': 'enemy', 'pos': [1, 1]},
                ])
        self.assertEqual(battle.units, [])
        self.assertEqual(battle.events, [])
        self.assertEqual(battle.lifetimes, {})

    def test_fallback_nearest_is_stable(self):
        battle = self.make_battle()
        with patch('sporebound.lifecycle.validate_actor'):
            spawn(battle, {'id': 'a', 'name': 'A', 'team': 'enemy', 'pos': [2, 2]})
            second = spawn(battle, {'id': 'b', 'name': 'B', 'team': 'enemy',
                                    'pos': [2, 2], 'fallback_nearest': True})
        self.assertEqual(second.pos, (2, 1))


if __name__ == '__main__':
    unittest.main()
