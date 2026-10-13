"""3.7.19C+: contextual actor/interactive object edits are atomic and replay-safe."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_object
from sporebound.editor import Document
from sporebound.entity_editing import (entities_at, get_entity, edit_entity,
                                       relocate_entity, duplicate_entity,
                                       remove_entity)
from sporebound.model import Content, RuleError
from sporebound.tactical_rpg3 import authored_rules_for_document


class EntityEditingTests(unittest.TestCase):
    def setUp(self):
        self.mid = 'entity_edit'
        self.data = add_blank_mission(
            Content.load(DEFAULT_CONTENT).to_dict(),
            self.mid, 'Scene de reference', 14, 14)

    def mission(self, data):
        return next(m for m in data['missions'] if m['id'] == self.mid)

    def actor(self, data, team='player'):
        return next(u for u in self.mission(data)['units'] if u['team'] == team)

    def test_pick_full_actor_footprint_and_multiple_overlapping_kinds(self):
        data = deepcopy(self.data)
        actor = self.actor(data)
        actor['pos'] = [3, 4]
        actor['footprint'] = [2, 2]
        self.assertEqual(
            [r.id for r in entities_at(data, self.mid, (4, 5))],
            [actor['id']])
        data = add_object(data, self.mid, 'supply', 'chest', (4, 5))
        self.assertEqual({r.kind for r in entities_at(data, self.mid, (4, 5))},
                         {'actor', 'object'})
        self.assertEqual(entities_at(data, self.mid, (9, 9)), ())
        with self.assertRaises(RuleError):
            entities_at(data, self.mid, (-1, 0))

    def test_edit_actor_facing_name_team_and_undo_redo_save(self):
        actor = self.actor(self.data)
        doc = Document(Content.from_dict(self.data))
        before = deepcopy(doc.data)
        doc.replace(edit_entity(doc.data, self.mid, 'actor', actor['id'],
                                name='Garde de Jeanne', facing='west', team='player'))
        result = get_entity(doc.data, self.mid, 'actor', actor['id'])
        self.assertEqual(result['name'], 'Garde de Jeanne')
        self.assertEqual(result['facing'], (-1, 0))
        with self.assertRaises(RuleError):
            edit_entity(doc.data, self.mid, 'actor', actor['id'], facing='up')
        with self.assertRaises(RuleError):
            edit_entity(doc.data, self.mid, 'actor', actor['id'], hp=10000)
        self.assertEqual(len(doc.undo_stack), 1)
        doc.undo()
        self.assertEqual(doc.data, before)
        doc.redo()
        self.assertEqual(get_entity(doc.data, self.mid, 'actor', actor['id'])['name'],
                         'Garde de Jeanne')
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'scene.json'
            doc.save(output)
            self.assertEqual(Content.load(output).to_dict(), doc.data)

    def test_door_switch_link_validation_and_remove_is_atomic(self):
        data = add_object(self.data, self.mid, 'gate', 'door', (6, 5))
        data = add_object(data, self.mid, 'lever', 'switch', (5, 5), link='gate')
        edited = edit_entity(data, self.mid, 'object', 'gate',
                             hp=35, locked=True)
        self.assertEqual(get_entity(edited, self.mid, 'object', 'gate')['hp'], 35)
        self.assertTrue(get_entity(edited, self.mid, 'object', 'gate')['locked'])
        self.assertEqual(get_entity(edited, self.mid, 'object', 'lever')['link'], 'gate')
        before = deepcopy(edited)
        for invalid in ({'hp': 0}, {'locked': 1}, {'kind': 'chest'}):
            with self.subTest(invalid=invalid), self.assertRaises(RuleError):
                edit_entity(edited, self.mid, 'object', 'gate', **invalid)
        with self.assertRaises(RuleError):
            edit_entity(edited, self.mid, 'object', 'lever', link='missing')
        with self.assertRaises(RuleError):
            remove_entity(edited, self.mid, 'object', 'gate')
        self.assertEqual(edited, before)
        detached = remove_entity(edited, self.mid, 'object', 'lever')
        removed = remove_entity(detached, self.mid, 'object', 'gate')
        self.assertFalse(self.mission(removed)['objects'])

    def test_patrol_translation_on_move_and_duplicate(self):
        data = deepcopy(self.data)
        actor = self.actor(data, team='enemy')
        actor['pos'] = [9, 3]
        actor['patrol_route'] = [[9, 2], [8, 2]]
        # Patrol waypoints can be authored independently of the behavior rule.
        Content.from_dict(data, rules=authored_rules_for_document(data))
        moved = relocate_entity(data, self.mid, 'actor', actor['id'], (7, 5))
        shifted = get_entity(moved, self.mid, 'actor', actor['id'])
        self.assertEqual(tuple(map(tuple, shifted['patrol_route'])), ((7, 4), (6, 4)))
        original = deepcopy(data)
        duplicate = duplicate_entity(data, self.mid, 'actor', actor['id'], (5, 7))
        new = next(u for u in self.mission(duplicate)['units'] if u['id'] != actor['id']
                   and u['team'] == 'enemy')
        self.assertEqual(tuple(map(tuple, new['patrol_route'])), ((5, 6), (4, 6)))
        self.assertEqual(new['ct'], 0)
        self.assertEqual(new['facing'], actor.get('facing', [0, 1]))
        self.assertEqual(data, original)
        with self.assertRaises(RuleError):
            relocate_entity(data, self.mid, 'actor', actor['id'], (13, 0))
        self.assertEqual(data, original)

    def test_defense_move_duplicate_and_passage_exit_absolute(self):
        data = add_object(self.data, self.mid, 'trap', 'defense', (4, 4))
        data = edit_entity(data, self.mid, 'object', 'trap',
                           team='player', power=33, charges=4, disabled=False)
        updated = relocate_entity(data, self.mid, 'object', 'trap', (5, 6))
        trap = get_entity(updated, self.mid, 'object', 'trap')
        self.assertEqual(trap['cells'], [[5, 6]])
        self.assertEqual(trap['power'], 33)
        duplicate = duplicate_entity(updated, self.mid, 'object', 'trap', (7, 8))
        copy = next(o for o in self.mission(duplicate)['objects']
                    if o['id'] != 'trap')
        self.assertNotEqual(copy['id'], 'trap')
        self.assertEqual(copy['cells'], [[7, 8]])
        self.assertEqual(copy['charges'], 4)
        data = add_object(self.data, self.mid, 'stairs', 'passage',
                          (3, 3), destination=(4, 4))
        moved = relocate_entity(data, self.mid, 'object', 'stairs', (3, 4))
        self.assertEqual(get_entity(moved, self.mid, 'object', 'stairs')['destination'],
                         [4, 4])
        with self.assertRaises(RuleError):
            edit_entity(moved, self.mid, 'object', 'stairs', destination='3,4')

    def test_last_team_actor_cannot_be_deleted(self):
        actor = self.actor(self.data, team='player')
        with self.assertRaises(RuleError):
            remove_entity(self.data, self.mid, 'actor', actor['id'])
        self.assertEqual(len(self.mission(self.data)['units']), 2)


if __name__ == '__main__':
    unittest.main()
