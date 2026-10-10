"""2.5.2 tactical graph is an editable view of the real trigger runtime."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.model import Content, RuleError
from sporebound import event_composer
from sporebound.event_graph import (add_action, build_event_graph, delete_event,
                                   duplicate_event, remove_action, reorder_action,
                                   reorder_event, update_action, update_condition)


class TacticalEventGraphTests(unittest.TestCase):
    def setUp(self):
        self.mid = 'garden'
        self.data = Content.load(DEFAULT_CONTENT).to_dict()
        self.before = deepcopy(self.data)

    def test_graph_has_ordered_real_condition_and_action_nodes(self):
        graph = build_event_graph(self.data, self.mid)
        mission = next(m for m in self.data['missions'] if m['id'] == self.mid)
        self.assertEqual(graph['total_events'], len(mission['triggers']))
        self.assertEqual(graph['drawn_events'], graph['total_events'])
        self.assertEqual(len(graph['nodes']),
                         sum(1+len(t['actions']) for t in mission['triggers']))
        self.assertEqual(len(graph['edges']),
                         sum(len(t['actions']) for t in mission['triggers']))
        for event in mission['triggers']:
            nodes = [n for n in graph['nodes'] if n['event_id'] == event['id']]
            self.assertEqual(nodes[0]['key'], (event['id'], 'condition'))
            self.assertEqual([n['index'] for n in nodes[1:]],
                             list(range(len(event['actions']))))
        self.assertEqual(self.data, self.before)

    def test_create_condition_edit_insert_and_reorder_is_atomic(self):
        updated = event_composer.save_event(
            self.data, self.mid, 'reinforcements',
            event_composer.condition('wave_capacity', max_alive=2),
            [event_composer.action('message', text='Portes ouvertes')])
        second = event_composer.action('hazard', pos=[2, 2], amount=3)
        updated = add_action(updated, self.mid, 'reinforcements', second)
        updated = reorder_action(updated, self.mid, 'reinforcements', 1, -1)
        mission = Content.from_dict(updated).missions[self.mid]
        event = next(e for e in mission.triggers if e['id'] == 'reinforcements')
        self.assertEqual(event['condition'], 'wave_capacity')
        self.assertEqual([a['kind'] for a in event['actions']], ['hazard', 'message'])
        updated = update_condition(updated, self.mid, 'reinforcements',
                                   event_composer.condition('tick', tick=5))
        updated = update_action(updated, self.mid, 'reinforcements', 1,
                                event_composer.action('status',
                                                      unit='ziggy', status='haste', duration=6))
        self.assertEqual(next(t for t in Content.from_dict(updated).missions[self.mid].triggers
                              if t['id']=='reinforcements')['actions'][1]['kind'], 'status')
        self.assertEqual(self.data, self.before)

    def test_invalid_replacements_do_not_mutate_source(self):
        updated = event_composer.save_event(
            self.data, self.mid, 'dialogue',
            event_composer.condition('tick', tick=8),
            [event_composer.action('message', text='Bonjour')])
        snapshot = deepcopy(updated)
        cases = [
            lambda: remove_action(updated, self.mid, 'dialogue', 0),
            lambda: reorder_action(updated, self.mid, 'dialogue', 0, 1),
            lambda: reorder_event(updated, self.mid, 'dialogue', 1),
            lambda: update_action(updated, self.mid, 'dialogue', 0,
                                  {'kind':'hazard', 'pos':[900, 0], 'amount':4}),
            lambda: update_condition(updated, self.mid, 'dialogue',
                                     {'condition':'defeated', 'unit':'missing'}),
            lambda: add_action(updated, self.mid, 'dialogue',
                               {'kind': 'unknown_event_action'}),
        ]
        for bad in cases:
            with self.subTest(bad=bad), self.assertRaises(RuleError):
                bad()
            self.assertEqual(updated, snapshot)

    def test_duplicate_and_remove_preserve_source_and_identity(self):
        source = event_composer.save_event(
            self.data, self.mid, 'announcement',
            event_composer.condition('tick', tick=7),
            [event_composer.action('message', text='Renforts!')])
        duplicate = duplicate_event(source, self.mid, 'announcement', 'announcement_alt')
        events = Content.from_dict(duplicate).missions[self.mid].triggers
        self.assertEqual(events[-1]['id'], 'announcement_alt')
        self.assertEqual(events[-1]['actions'], events[-2]['actions'])
        without = delete_event(duplicate, self.mid, 'announcement')
        self.assertNotIn('announcement', [e['id'] for e in
                                          Content.from_dict(without).missions[self.mid].triggers])
        self.assertEqual(source['missions'][0]['triggers'][-1]['id'], 'announcement')
        with self.assertRaises(RuleError):
            duplicate_event(source, self.mid, 'announcement', 'announcement')

    def test_reorder_event_changes_runtime_priority_only(self):
        data = event_composer.save_event(self.data, self.mid, 'first_rule',
                     event_composer.condition('tick', tick=0),
                     [event_composer.action('message', text='premier')])
        data = event_composer.save_event(data, self.mid, 'second_rule',
                     event_composer.condition('tick', tick=0),
                     [event_composer.action('message', text='second')])
        result = reorder_event(data, self.mid, 'second_rule', -1)
        ids = [e['id'] for e in Content.from_dict(result).missions[self.mid].triggers]
        self.assertEqual(ids[-3:-1], ['second_rule', 'first_rule'])
        self.assertEqual(self.data, self.before)
        # The view is not a second serialization or a different runtime format.
        self.assertEqual(Content.from_dict(result).to_dict(), result)

    def test_wave_and_queue_wave_use_existing_trigger_contracts(self):
        data = deepcopy(self.data)
        data.setdefault('archetypes', {})['light_foe'] = {'max_hp': 24, 'hp': 24}
        a = event_composer.action('queue_wave', pos=(2, 0), actor_id='wave_f1',
                                  archetype='light_foe', name='Garde')
        b = event_composer.action('wave', pos=(2, 1), actor_id='wave_f2',
                                  archetype='light_foe', name='Sentinelle',
                                  max_active=5)
        for action in (a, b):
            updated = event_composer.save_event(
                data, self.mid, 'wave_demo',
                event_composer.condition('tick', tick=50), [action])
            self.assertIn('wave_demo', [t['id'] for t in
                                       Content.from_dict(updated).missions[self.mid].triggers])
        with self.assertRaises(RuleError):
            duplicate_event(updated, self.mid, 'wave_demo', 'other_wave')

    def test_graph_budget_is_deterministic(self):
        graph = build_event_graph(self.data, self.mid, max_nodes=2)
        self.assertTrue(graph['truncated'])
        self.assertLessEqual(len(graph['nodes']), 2)
        for invalid in (0, -1, True, 3001):
            with self.assertRaises(RuleError):
                build_event_graph(self.data, self.mid, max_nodes=invalid)


if __name__ == '__main__':
    unittest.main()
