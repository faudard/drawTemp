"""Interior Builder 2.0: enter a tower, change deck, fight, save and replay.

The test exercises authored geometry and the *real* Battle/Storage interfaces,
not a miniature reimplementation of layered navigation.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.layered_tower_3720_gate import create
from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import Document
from sporebound.engine import Battle
from sporebound.interior_levels import edit_interior_tile
from sporebound.model import Content, RuleError
from sporebound.storage import load_battle, save_battle


class InteriorBuilderTowerGate(unittest.TestCase):
    def setUp(self):
        self.data, self.mid = create()
        self.content = Content.from_dict(self.data)
        self.mission = self.content.missions[self.mid]
        self.hero = next(u.id for u in self.mission.units if u.team == 'player')
        self.enemy = next(u.id for u in self.mission.units if u.team == 'enemy')

    def battle(self):
        battle = Battle(self.content, self.mid, seed=7, battle_id='tower-gate')
        self.assertEqual(battle.active_id, self.hero)
        return battle

    def test_tower_entry_fight_checkpoint_and_replay(self):
        battle = self.battle()
        # Upper and lower occupancies must not leak across floor boundaries.
        self.assertEqual(battle.at((4, 4)), None)
        self.assertEqual(battle.at((4, 4), level=1).id, self.enemy)
        initial = battle.digest()
        with self.assertRaises(RuleError):
            battle.execute({'kind': 'act', 'skill': 'attack', 'cell': [4, 4]})
        self.assertEqual(battle.digest(), initial)
        self.assertIn((1, 4, 5), battle.level_reachable())
        battle.execute({'kind': 'level_move', 'level': 1, 'cell': [4, 5]})
        self.assertEqual(battle.unit_levels[self.hero], 1)
        self.assertEqual(battle.unit(self.hero).pos, (4, 5))
        self.assertEqual(battle.at((4, 4), level=1).id, self.enemy)
        battle.execute({'kind': 'act', 'skill': 'attack', 'cell': [4, 4]})
        self.assertEqual([row['kind'] for row in battle.commands[-2:]],
                         ['level_move', 'act'])
        self.assertTrue(any(row['kind'] == 'skill' for row in battle.events))
        expected_digest = battle.digest()
        self.assertEqual(Battle.replay(battle.recording()).digest(),
                         expected_digest)

        with TemporaryDirectory() as folder:
            content_path = Path(folder) / 'tower_content.json'
            checkpoint = Path(folder) / 'tower_checkpoint.json'
            Document(self.content).save(content_path)
            self.assertEqual(Content.load(content_path).to_dict(), self.data)
            save_battle(checkpoint, battle)
            restored = load_battle(checkpoint)
            self.assertEqual(restored.digest(), expected_digest)
            self.assertEqual(restored.unit_levels, battle.unit_levels)
            self.assertEqual(Battle.replay(restored.recording()).digest(),
                             expected_digest)

    def test_tile_elevation_is_not_floor_identity(self):
        # The Tower preset has a raised central tile on N0; it is *not* N2.
        self.assertEqual(self.mission.board.tile((4, 4)).height, 2)
        self.assertEqual(self.mission.unit_levels[self.enemy], 1)
        battle = self.battle()
        self.assertEqual(battle.unit_levels.get(self.hero, 0), 0)
        self.assertIsNone(battle.at((4, 4), level=2))
        self.assertIn((1, 4, 5), battle.level_reachable())
        self.assertNotIn((2, 4, 4), battle.level_reachable())

    def test_upper_floor_edit_does_not_mutate_ground_or_legacy_schema(self):
        ground = self.mission.board.tile((4, 4)).to_dict()
        sid = self.mission.structures[0]['id']
        updated = edit_interior_tile(self.data, self.mid, sid, 1, (4, 4),
                                     feature='crate')
        new_mission = Content.from_dict(updated).missions[self.mid]
        self.assertEqual(new_mission.board.tile((4, 4)).to_dict(), ground)
        self.assertEqual(self.mission.board.tile((4, 4)).to_dict(), ground)
        legacy = Content.load(DEFAULT_CONTENT).to_dict()
        self.assertEqual(Content.from_dict(legacy).to_dict(), legacy)


if __name__ == '__main__':
    unittest.main()
