"""3.7.20C: vertical navigation, floor-scoped attacks and exact replay."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.engine import Battle
from sporebound.interior_levels import add_interior_floor
from sporebound.iso_structures import place_structure
from sporebound.level_navigation import (
    add_level_link, place_unit_on_level, remove_level_link,
    available_level_moves)
from sporebound.model import Content, RuleError
from sporebound.storage import save_battle, load_battle


class TacticalFloorTests(unittest.TestCase):
    MID = 'tactical_floors_3720c'

    def setUp(self):
        base = Content.load(DEFAULT_CONTENT).to_dict()
        data = add_blank_mission(base, self.MID, 'Tour tactique', 16, 16)
        data = place_structure(data, self.MID, 'Maison', (3, 3))
        self.sid = next(m for m in data['missions']
                        if m['id'] == self.MID)['structures'][0]['id']
        data = add_interior_floor(data, self.MID, self.sid, 1)
        data = add_level_link(data, self.MID, [0, 4, 5], [1, 4, 5])
        raw = next(m for m in data['missions'] if m['id'] == self.MID)
        self.player = next(u['id'] for u in raw['units'] if u['team'] == 'player')
        self.enemy = next(u['id'] for u in raw['units'] if u['team'] == 'enemy')
        data = place_unit_on_level(data, self.MID, self.player, 0, (4, 5))
        data = place_unit_on_level(data, self.MID, self.enemy, 1, (4, 4))
        for row in next(m for m in data['missions'] if m['id'] == self.MID)['units']:
            row['speed'] = 1000 if row['team'] == 'player' else 1
        self.doc = Document(Content.from_dict(data))
        self.assertEqual(self.doc.playtest(self.MID, seed=7).active_id, self.player)

    def battle(self):
        return self.doc.playtest(self.MID, seed=7)

    def test_can_traverse_stairs_and_attack_only_on_same_floor(self):
        battle = self.battle()
        self.assertEqual(battle.unit_levels[self.enemy], 1)
        self.assertIsNone(battle.at((4, 4)))
        self.assertEqual(battle.at((4, 4), level=1).id, self.enemy)
        with self.assertRaises(RuleError):
            battle.execute({'kind': 'act', 'skill': 'attack', 'cell': [4, 4]})
        self.assertFalse(battle.active.acted)
        self.assertEqual(battle.unit_levels.get(self.player, 0), 0)
        self.assertIn((1, 4, 5), battle.level_reachable())
        battle.execute({'kind': 'level_move', 'level': 1, 'cell': [4, 5]})
        self.assertEqual(battle.unit_levels[self.player], 1)
        self.assertTrue(battle.unit(self.player).moved)
        self.assertEqual(battle.unit(self.player).pos, (4, 5))
        self.assertNotIn((1, 4, 4), battle.level_reachable())
        battle.execute({'kind': 'act', 'skill': 'attack', 'cell': [4, 4]})
        self.assertTrue(any(e['kind'] == 'skill' for e in battle.events))
        self.assertEqual(battle.commands[-2]['kind'], 'level_move')

    def test_vertical_move_is_atomic_and_refuses_missing_links(self):
        battle = self.battle()
        before = battle.digest()
        commands = len(battle.commands)
        for command in (
            {'kind': 'level_move', 'level': 2, 'cell': [4, 5]},
            {'kind': 'level_move', 'level': 1, 'cell': [4, 4]},
            {'kind': 'level_move', 'level': True, 'cell': [4, 5]},
            {'kind': 'move', 'cell': [4, 4]},
        ):
            # Last command might be a valid ground move; only the first
            # three are necessarily invalid here.
            if command['kind'] == 'move':
                continue
            with self.subTest(command=command), self.assertRaises(RuleError):
                battle.execute(command)
            self.assertEqual(battle.digest(), before)
            self.assertEqual(len(battle.commands), commands)

    def test_stacked_ground_occupancy_and_save_replay(self):
        self.doc.replace(place_unit_on_level(
            self.doc.data, self.MID, self.player, 0, (4, 4)))
        scene = Content.from_dict(self.doc.data).missions[self.MID]
        self.assertEqual(scene.units[0].pos, (4, 4))
        battle = self.battle()
        self.assertEqual(battle.at((4, 4), level=0).id, self.player)
        self.assertEqual(battle.at((4, 4), level=1).id, self.enemy)
        self.assertIn((1, 4, 5), battle.level_reachable())
        battle.execute({'kind': 'level_move', 'level': 1, 'cell': [4, 5]})
        restored = Battle.replay(battle.recording())
        self.assertEqual(restored.digest(), battle.digest())
        self.assertEqual(restored.unit_levels, battle.unit_levels)
        with TemporaryDirectory() as folder:
            content_path = Path(folder) / 'content.json'
            checkpoint = Path(folder) / 'battle.json'
            self.doc.save(content_path)
            self.assertEqual(Content.load(content_path).to_dict(), self.doc.data)
            save_battle(checkpoint, battle)
            self.assertEqual(load_battle(checkpoint).digest(), battle.digest())

    def test_invalid_connector_is_rejected_without_any_edit(self):
        original = deepcopy(self.doc.data)
        for start, end in (
            ([0, 0, 0], [1, 4, 5]),
            ([0, 4, 5], [3, 4, 5]),
            ([0, 4, 5], [1, 15, 15]),
            ([0, 4, 5], [1, 4, 5]),
        ):
            with self.subTest(start=start, end=end), self.assertRaises(RuleError):
                add_level_link(original, self.MID, start, end)
        self.assertEqual(self.doc.data, original)

    def test_invalid_upper_spawn_does_not_modify_document(self):
        original = deepcopy(self.doc.data)
        for cell, level in (((8, 8), 1), ((4, 4), 3), ((3, 3), 1)):
            with self.subTest(cell=cell, level=level), self.assertRaises(RuleError):
                place_unit_on_level(original, self.MID, self.player, level, cell)
        self.assertEqual(self.doc.data, original)

    def test_connector_removal_and_legacy_content_serialization(self):
        self.doc.replace(remove_level_link(self.doc.data, self.MID, 'stair_1'))
        self.assertEqual(self.doc.data['version'], 1)
        self.doc.undo()
        self.assertEqual(self.doc.data['version'], 1)
        with self.assertRaises(RuleError):
            self.doc.replace(remove_level_link(self.doc.data, self.MID, 'missing'))

        legacy = Content.load(DEFAULT_CONTENT).to_dict()
        self.assertEqual(Content.from_dict(legacy).to_dict(), legacy)
        self.assertFalse(any('level_links' in row or 'unit_levels' in row
                             for row in legacy['missions']))


if __name__ == '__main__':
    unittest.main()
