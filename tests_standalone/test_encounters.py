"""Tests for bounded encounter wave scheduling."""
import unittest
from sporebound.encounters import EncounterDirector
from sporebound.model import RuleError


class FakeUnit:
    def __init__(self, alive=True, id="fake"):
        self.alive = alive
        self.id = id

    def occupied_cells(self):
        return set()


class FakeBattle:
    def __init__(self, count):
        self.units = [FakeUnit() for _ in range(count)]
        self.events = []

    def spawn_wave(self, actors, *, lifetime=None, max_active=14):
        spawned = [FakeUnit() for _ in actors]
        self.units.extend(spawned)
        return spawned

    def emit(self, kind, **data):
        self.events.append({"kind": kind, **data})


class EncounterTests(unittest.TestCase):
    def test_wave_waits_until_capacity_available(self):
        director = EncounterDirector(max_active=4)
        battle = FakeBattle(3)
        director.queue([{"id": "a", "pos": [1, 1]}, {"id": "b", "pos": [2, 1]}])
        self.assertEqual(director.dispatch(battle), [])
        self.assertEqual(len(director.pending), 1)
        battle.units[0].alive = False
        self.assertEqual(len(director.dispatch(battle)), 2)
        self.assertEqual(len(director.pending), 0)

    def test_fifo_does_not_skip_blocked_wave(self):
        director = EncounterDirector(max_active=4)
        battle = FakeBattle(3)
        director.queue([{"id": "a"}, {"id": "b"}])
        director.queue([{"id": "c", "pos": [3, 1]}])
        self.assertEqual(director.dispatch(battle), [])
        self.assertEqual(len(director.pending), 2)

    def test_reject_oversized_wave(self):
        director = EncounterDirector(max_active=2)
        with self.assertRaises(RuleError):
            director.queue([{}, {}, {}])


if __name__ == "__main__":
    unittest.main()
