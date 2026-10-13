"""3.7.21C: contextual authoring must stay a projection of engine contracts."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound import event_composer, event_context
from sporebound.model import Content, RuleError


class ContextualEventPreviewTests(unittest.TestCase):
    def setUp(self):
        self.data = Content.load(DEFAULT_CONTENT).to_dict()
        self.mid = 'garden'
        self.data = event_composer.save_event(
            self.data, self.mid, 'gate_test',
            event_composer.condition('tick', tick=5),
            [event_composer.action('message', text='Porte ouverte'),
             event_composer.action('hazard', pos=[0, 0], amount=2)])

    def test_inspection_is_read_only_and_links_have_mission_scope(self):
        snapshot = deepcopy(self.data)
        project = SimpleNamespace(
            story={'after_mission': {'garden': 'victory_scene'}},
            cinematics=[
                {'id': 'cin_before', 'trigger': {
                    'kind': 'before_mission', 'target': 'garden'}},
                {'id': 'cin_after', 'trigger': {
                    'kind': 'after_mission', 'target': 'garden'}},
                {'id': 'elsewhere', 'trigger': {
                    'kind': 'scene', 'target': 'victory_scene'}},
            ])
        context = event_context.inspect_event(
            self.data, self.mid, 'gate_test', project)
        self.assertEqual(context['scene_id'], 'victory_scene')
        self.assertEqual(context['cinematics'], [
            {'id': 'cin_before', 'stage': 'before_mission'},
            {'id': 'cin_after', 'stage': 'after_mission'}])
        self.assertEqual(context['links_scope'], 'mission')
        self.assertEqual(context['actions'][0], 'Message : Porte ouverte')
        self.assertEqual(self.data, snapshot)

    def test_real_dispatch_respects_condition_and_action_order(self):
        snapshot = deepcopy(self.data)
        before = event_context.preview_event(
            self.data, self.mid, 'gate_test', tick=4)
        self.assertFalse(before['fired'])
        self.assertEqual(before['events'], [])
        after = event_context.preview_event(
            self.data, self.mid, 'gate_test', tick=5)
        self.assertTrue(after['fired'])
        self.assertTrue(after['isolated'])
        self.assertEqual([row['kind'] for row in after['events']],
                         ['trigger', 'message'])
        self.assertEqual(after['events'][1]['text'], 'Porte ouverte')
        self.assertEqual(after['error'], '')
        self.assertEqual(self.data, snapshot)

    def test_invalid_references_and_clock_do_not_mutate_source(self):
        initial = deepcopy(self.data)
        for tick in (-1, 100001, True, 1.5):
            with self.subTest(tick=tick), self.assertRaises(RuleError):
                event_context.preview_event(
                    self.data, self.mid, 'gate_test', tick=tick)
        with self.assertRaises(RuleError):
            event_context.inspect_event(self.data, 'unknown', 'gate_test')
        with self.assertRaises(RuleError):
            event_context.preview_event(self.data, self.mid, 'missing')
        self.assertEqual(self.data, initial)

    def test_preview_does_not_run_other_triggers(self):
        self.data = event_composer.save_event(
            self.data, self.mid, 'another_event',
            event_composer.condition('tick', tick=0),
            [event_composer.action('message', text='Unrelated')])
        report = event_context.preview_event(
            self.data, self.mid, 'gate_test', tick=10)
        self.assertEqual(
            [entry.get('text') for entry in report['events']
             if entry['kind'] == 'message'], ['Porte ouverte'])


if __name__ == '__main__':
    unittest.main()
