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
            {'id': 'cin_before', 'stage': 'before_mission', 'scope': 'mission'},
            {'id': 'cin_after', 'stage': 'after_mission', 'scope': 'mission'},
            {'id': 'elsewhere', 'stage': 'scene', 'scope': 'scene'}])
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


    def test_tick_scenarios_use_real_rule_and_reject_impossible_false(self):
        true_case = event_context.preview_event(
            self.data, self.mid, 'gate_test', scenario='satisfied')
        false_case = event_context.preview_event(
            self.data, self.mid, 'gate_test', scenario='unsatisfied')
        self.assertEqual(true_case['tick'], 5)
        self.assertEqual(false_case['tick'], 4)
        self.assertTrue(true_case['fired'])
        self.assertEqual(true_case['outcome'], 'applied')
        self.assertFalse(false_case['fired'])
        self.assertEqual(false_case['outcome'], 'inactive')
        self.assertTrue(any('danger' in row for row in true_case['changes']))
        self.assertFalse(false_case['changes'])
        self.assertTrue(any('CONSÉQUENCES' in line for line in
                            event_context.format_preview_report(true_case)))
        zero = event_composer.save_event(
            self.data, self.mid, 'tick_zero',
            event_composer.condition('tick', tick=0),
            [event_composer.action('message', text='always')])
        with self.assertRaisesRegex(RuleError, 'always true'):
            event_context.preview_event(
                zero, self.mid, 'tick_zero', scenario='unsatisfied')

    def test_hp_and_defeat_cases_change_only_synthetic_actor_state(self):
        unit_id = next(m for m in self.data['missions'] if m['id'] == self.mid)['units'][0]['id']
        original = deepcopy(self.data)
        for condition in (
            event_composer.condition('hp_below', unit=unit_id, percent=50),
            event_composer.condition('defeated', unit=unit_id),
        ):
            with self.subTest(condition=condition):
                data = event_composer.save_event(
                    self.data, self.mid, 'boss_gate', condition,
                    [event_composer.action('message', text='Boss phase')])
                yes = event_context.preview_event(
                    data, self.mid, 'boss_gate', scenario='satisfied')
                no = event_context.preview_event(
                    data, self.mid, 'boss_gate', scenario='unsatisfied')
                self.assertTrue(yes['fired'], yes)
                self.assertFalse(no['fired'], no)
                self.assertEqual(yes['changes'], [])
                self.assertEqual(self.data, original)

    def test_entry_and_capacity_cases_are_dispatched_by_engine(self):
        mission = next(m for m in self.data['missions'] if m['id'] == self.mid)
        self.assertTrue(any(u['team'] == 'player' for u in mission['units']))
        self.assertTrue(any(u['team'] == 'enemy' for u in mission['units']))
        entry = event_composer.save_event(
            self.data, self.mid, 'entry_probe',
            event_composer.condition('enter', pos=[0, 0]),
            [event_composer.action('message', text='Entered')])
        yes = event_context.preview_event(
            entry, self.mid, 'entry_probe', scenario='satisfied')
        no = event_context.preview_event(
            entry, self.mid, 'entry_probe', scenario='unsatisfied')
        self.assertTrue(yes['fired'])
        self.assertFalse(no['fired'])
        wave = event_composer.save_event(
            self.data, self.mid, 'capacity_probe',
            event_composer.condition('wave_capacity', team='enemy', max_alive=0),
            [event_composer.action('message', text='Clear')])
        self.assertTrue(event_context.preview_event(
            wave, self.mid, 'capacity_probe', scenario='satisfied')['fired'])
        self.assertFalse(event_context.preview_event(
            wave, self.mid, 'capacity_probe', scenario='unsatisfied')['fired'])

    def test_status_and_hazard_are_visible_in_differences(self):
        unit_id = next(u['id'] for u in next(m for m in self.data['missions'] if m['id'] == self.mid)['units']
                       if u['team'] == 'player')
        data = event_composer.save_event(
            self.data, self.mid, 'state_diffs',
            event_composer.condition('tick', tick=5),
            [event_composer.action('status', unit=unit_id,
                                   status='haste', duration=5),
             event_composer.action('hazard', pos=[0, 0], amount=9)])
        report = event_context.preview_event(
            data, self.mid, 'state_diffs', scenario='satisfied')
        self.assertTrue(report['fired'])
        self.assertEqual(report['outcome'], 'applied')
        self.assertTrue(any('statuts' in row for row in report['changes']))
        self.assertTrue(any('danger' in row for row in report['changes']))

    def test_invalid_scenario_does_not_change_document(self):
        original = deepcopy(self.data)
        with self.assertRaises(RuleError):
            event_context.preview_event(
                self.data, self.mid, 'gate_test', scenario='custom_script')
        self.assertEqual(original, self.data)



    def test_action_runtime_failure_is_reported_not_confused_with_unmet_gate(self):
        data = event_composer.save_event(
            self.data, self.mid, 'action_failure',
            event_composer.condition('tick', tick=5),
            [event_composer.action('message', text='Before failure'),
             event_composer.action('despawn', unit='absent_runtime_actor')])
        original = deepcopy(data)
        report = event_context.preview_event(
            data, self.mid, 'action_failure', scenario='satisfied')
        self.assertTrue(report['fired'])
        self.assertEqual(report['outcome'], 'error')
        self.assertTrue(report['error'])
        self.assertEqual(report['events'][0]['kind'], 'trigger')
        self.assertEqual(report['events'][1]['kind'], 'message')
        self.assertIn('ERREUR', '\n'.join(event_context.format_preview_report(report)))
        self.assertEqual(data, original)


if __name__ == '__main__':
    unittest.main()
