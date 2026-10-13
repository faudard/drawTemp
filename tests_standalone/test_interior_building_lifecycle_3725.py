"""3.7.25: structure edits must never orphan interior decks or stair routes."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.engine import Battle
from sporebound.interior_levels import add_interior_floor, delete_interior_floor
from sporebound.iso_structures import (
    edit_structure, move_structure, place_structure, remove_structure,
    structure_at, validate_structure_edit)
from sporebound.level_navigation import (
    add_level_link, place_unit_on_level, remove_level_link)
from sporebound.model import Content, RuleError
from sporebound.storage import load_battle, save_battle
from sporebound.structure_groups import transform_structure_group


class InteriorBuildingLifecycleTests(unittest.TestCase):
    MID = 'interior_building_lifecycle'

    def setUp(self):
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 self.MID, 'Tour et escalier', 18, 18)
        data = place_structure(data, self.MID, 'Maison', (3, 3))
        self.sid = next(row for row in data['missions']
                        if row['id'] == self.MID)['structures'][0]['id']
        data = add_interior_floor(data, self.MID, self.sid, 1)
        data = add_level_link(data, self.MID, [0, 4, 5], [1, 4, 5])
        mission = next(row for row in data['missions'] if row['id'] == self.MID)
        self.hero = next(u['id'] for u in mission['units'] if u['team'] == 'player')
        self.foe = next(u['id'] for u in mission['units'] if u['team'] == 'enemy')
        data = place_unit_on_level(data, self.MID, self.foe, 1, (4, 4))
        mission = next(row for row in data['missions'] if row['id'] == self.MID)
        for unit in mission['units']:
            unit['speed'] = 1000 if unit['id'] == self.hero else 1
        self.doc = Document(Content.from_dict(data))

    def raw_mission(self, data=None):
        return next(row for row in (data or self.doc.data)['missions']
                    if row['id'] == self.MID)

    def test_move_translates_own_stairs_upper_actor_and_preserves_deck(self):
        before = deepcopy(self.doc.data)
        moved = move_structure(before, self.MID, (4, 4), (6, 3))
        self.assertEqual(before, self.doc.data, 'Input may not mutate')
        self.doc.replace(moved)
        mission = self.raw_mission()
        building = structure_at(moved, self.MID, (7, 4))
        self.assertEqual((building.id, building.anchor), (self.sid, (6, 3)))
        self.assertEqual(mission['interior_floors'][0]['structure_id'], self.sid)
        self.assertEqual(mission['level_links'][0]['from'], [0, 7, 5])
        self.assertEqual(mission['level_links'][0]['to'], [1, 7, 5])
        foe = next(u for u in mission['units'] if u['id'] == self.foe)
        self.assertEqual(foe['pos'], [7, 4])
        self.assertEqual(mission['unit_levels'][self.foe], 1)
        self.assertEqual(Content.from_dict(moved).to_dict(), moved)
        self.doc.undo()
        self.assertEqual(self.doc.data, before)
        self.doc.redo()
        self.assertEqual(self.doc.data, moved)

    def test_enter_move_fight_and_checkpoint_after_edit(self):
        data = move_structure(self.doc.data, self.MID, (4, 4), (6, 3))
        data = place_unit_on_level(data, self.MID, self.hero, 0, (7, 5))
        battle = Battle(Content.from_dict(data), self.MID, seed=7,
                        battle_id='moved-house-level-test')
        self.assertEqual(battle.active_id, self.hero)
        self.assertEqual(battle.at((7, 4), level=1).id, self.foe)
        self.assertIsNone(battle.at((7, 4), level=0))
        self.assertIn((1, 7, 5), battle.level_reachable())
        before = battle.digest()
        with self.assertRaises(RuleError):
            battle.execute({'kind': 'act', 'skill': 'attack', 'cell': [7, 4]})
        self.assertEqual(before, battle.digest())
        battle.execute({'kind': 'level_move', 'level': 1, 'cell': [7, 5]})
        battle.execute({'kind': 'act', 'skill': 'attack', 'cell': [7, 4]})
        self.assertEqual(battle.unit_levels[self.hero], 1)
        digest = battle.digest()
        self.assertEqual(Battle.replay(battle.recording()).digest(), digest)
        with TemporaryDirectory() as folder:
            checkpoint = Path(folder) / 'save.json'
            save_battle(checkpoint, battle)
            restored = load_battle(checkpoint)
            self.assertEqual(restored.digest(), digest)
            self.assertEqual(restored.unit_levels, battle.unit_levels)

    def test_incompatible_geometry_change_fails_before_edit(self):
        before = deepcopy(self.doc.data)
        for kwargs in ({'quarter_turns': 1}, {'name': 'Tour'},
                       {'door_slot': 1}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(
                    RuleError, 'remap'):
                validate_structure_edit(before, self.MID, (4, 4), **kwargs)
            with self.assertRaises(RuleError):
                edit_structure(before, self.MID, (4, 4), **kwargs)
        self.assertEqual(before, self.doc.data)

    def test_links_and_occupants_must_be_removed_before_deletion(self):
        before = deepcopy(self.doc.data)
        for action in (
            lambda data: remove_structure(data, self.MID, (4, 4)),
            lambda data: delete_interior_floor(data, self.MID, self.sid, 1),
        ):
            with self.assertRaises(RuleError):
                action(before)
        self.assertEqual(before, self.doc.data)
        data = place_unit_on_level(before, self.MID, self.foe, 0, (9, 9))
        with self.assertRaisesRegex(RuleError, 'stair'):
            delete_interior_floor(data, self.MID, self.sid, 1)
        data = remove_level_link(data, self.MID, 'stair_1')
        data = delete_interior_floor(data, self.MID, self.sid, 1)
        data = remove_structure(data, self.MID, (4, 4))
        self.assertFalse(self.raw_mission(data).get('interior_floors'))
        self.assertFalse(self.raw_mission(data).get('structures'))
        Content.from_dict(data)

    def test_group_move_is_rejected_until_floor_remap_is_supported(self):
        building = structure_at(self.doc.data, self.MID, (4, 4))
        old = deepcopy(self.doc.data)
        with self.assertRaisesRegex(RuleError, 'individually'):
            transform_structure_group(
                old, self.MID, list(building.cells), 2, 0)
        self.assertEqual(old, self.doc.data)

    def test_legacy_documents_remain_byte_equivalent_after_roundtrip(self):
        raw = Content.load(DEFAULT_CONTENT).to_dict()
        self.assertEqual(Content.from_dict(raw).to_dict(), raw)


if __name__ == '__main__':
    unittest.main()
