"""3.1 regression: hierarchical tactical predicates edit canonical Mission.triggers."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.entity_event_studio import author_gate_sequence
from sporebound.event_composer import action, condition, save_event
from sporebound.event_context import preview_event, format_preview_report
from sporebound.event_graph import (
    composite_at, composite_nodes, edit_composite_node,
    extend_condition, clear_composite_condition)
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError


class EventConditionTreeTests(unittest.TestCase):
    def setUp(self):
        self.raw = Content.load(DEFAULT_CONTENT).to_dict()
        self.mid = 'garden'
        self.initial = deepcopy(self.raw)
        self.data = save_event(
            self.raw, self.mid, 'tree_event',
            condition('tick', tick=5),
            [action('message', text='Une alerte')])

    def event(self, data):
        return next(e for m in data['missions'] if m['id'] == self.mid
                    for e in m['triggers'] if e['id'] == 'tree_event')

    def change(self, data, path, operation, **kwargs):
        return edit_composite_node(
            data, self.mid, 'tree_event', path,
            operation=operation, **kwargs)

    def test_tree_edit_replace_negate_reorder_remove_and_undo_equivalence(self):
        base = deepcopy(self.data)
        data = extend_condition(
            base, self.mid, 'tree_event', condition('tick', tick=7))
        self.assertEqual(composite_nodes(self.event(data))[0]['path'], ())
        data = self.change(data, (), 'wrap', join='all',
                           predicate=condition('wave_capacity', max_alive=100))
        self.assertEqual([n['path'] for n in composite_nodes(self.event(data))],
                         [(), (0,), (1,)])
        self.assertEqual(composite_at(self.event(data), (1,))['condition'],
                         'wave_capacity')
        data = self.change(data, (0,), 'replace',
                           predicate=condition('tick', tick=2))
        data = self.change(data, (1,), 'negate')
        self.assertIn('not', composite_at(self.event(data), (1,)))
        self.assertEqual([n['path'] for n in composite_nodes(self.event(data))],
                         [(), (0,), (1,), (1, 0)])
        data = self.change(data, (1,), 'move', direction=-1)
        self.assertIn('not', composite_at(self.event(data), (0,)))
        data = self.change(data, (0,), 'remove')
        self.assertEqual(composite_at(self.event(data)),
                         condition('tick', tick=2))
        data = self.change(data, (), 'remove')
        self.assertNotIn('when', self.event(data))
        self.assertEqual(data, base)
        self.assertEqual(self.raw, self.initial)
        self.assertEqual(Content.from_dict(data).to_dict(), data)

    def test_invalid_paths_unregistered_leaves_depth_and_group_bounds(self):
        data = extend_condition(
            self.data, self.mid, 'tree_event', condition('tick', tick=3))
        before = deepcopy(data)
        invalid = [
            lambda: self.change(data, (2,), 'remove'),
            lambda: self.change(data, (0,), 'remove'),
            lambda: self.change(data, (), 'move', direction=1),
            lambda: self.change(data, (), 'replace',
                                predicate={'condition': 'invalid'}),
            lambda: self.change(data, (), 'wrap',
                                predicate={'condition': 'no_rule'}),
            lambda: self.change(data, (), 'negate', direction=9) if False
                    else composite_at(self.event(data), ('bad',)),
        ]
        for op in invalid:
            with self.subTest(op=op), self.assertRaises(RuleError):
                op()
            self.assertEqual(data, before)
        deep = data
        for n in range(3):
            deep = self.change(deep, (), 'wrap', join='all',
                               predicate=condition('tick', tick=n))
        with self.assertRaises(RuleError):
            self.change(deep, (), 'wrap', join='all',
                        predicate=condition('tick', tick=3))
        self.assertEqual(data, before)

    def test_diagnostic_reads_real_predicates_before_actions(self):
        data = extend_condition(
            self.data, self.mid, 'tree_event',
            condition('wave_capacity', max_alive=100))
        initial = preview_event(data, self.mid, 'tree_event',
                                tick=0, scenario='initial')
        self.assertFalse(initial['condition_passed'])
        self.assertFalse(initial['fired'])
        self.assertEqual([(n['path'], n['passed']) for n in
                          initial['condition_trace']],
                         [('primary', False), ((), True)])
        active = preview_event(data, self.mid, 'tree_event',
                               scenario='satisfied')
        self.assertTrue(active['condition_passed'])
        self.assertTrue(active['fired'])
        self.assertEqual(active['outcome'], 'applied')
        self.assertIn('DIAGNOSTIC DES CONDITIONS',
                      '\n'.join(format_preview_report(active)))
        self.assertEqual(data['version'], 1)

    def test_interaction_diagnostic_uses_real_command_and_replayable_trigger(self):
        project = GameProject.default(Content.from_dict(self.raw))
        staged, project = author_gate_sequence(
            self.raw, project, self.mid, door_id='gate',
            lever_id='switch', lever_cell=[2, 4],
            event_id='tree_gate', danger_cell=[5, 5],
            min_tick=3, danger=6)
        before = deepcopy(staged)
        report = preview_event(staged, self.mid, 'tree_gate',
                               scenario='satisfied', include_scene=True)
        self.assertTrue(report['condition_passed'], report['diagnostic_error'])
        self.assertEqual([n['passed'] for n in report['condition_trace']],
                         [True, True])
        self.assertTrue(report['fired'])
        self.assertIn('tree_gate', report['scene_after'].fired)
        self.assertEqual(staged, before)
        self.assertEqual(project.cinematics[0]['id'], 'cin_tree_gate')

    def test_delete_a_not_child_removes_not_and_collapses_parent(self):
        data = extend_condition(
            self.data, self.mid, 'tree_event', condition('tick', tick=5))
        data = self.change(data, (), 'wrap', join='all',
                           predicate=condition('tick', tick=10))
        data = self.change(data, (1,), 'negate')
        cleared = self.change(data, (1, 0), 'remove')
        self.assertEqual(composite_at(self.event(cleared)),
                         condition('tick', tick=5))


if __name__ == '__main__':
    unittest.main()
