"""3.5A: deterministic temporal trigger gates, cancellation and authoring."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.event_composer import action, condition, save_event
from sporebound.event_graph import (
    configure_schedule, link_event, update_condition, condition_summary)
from sporebound.model import Content, RuleError
from sporebound.rules import triggers
from sporebound.temporal_events import temporal_status


class TemporalEvents35ATests(unittest.TestCase):
    def setUp(self):
        data = Content.load(DEFAULT_CONTENT).to_dict()
        self.mid = 'garden'
        data = save_event(data, self.mid, 'clock_start',
                          condition('tick', tick=0),
                          [action('message', text='Signal')])
        data = save_event(data, self.mid, 'clock_end',
                          condition('tick', tick=0),
                          [action('message', text='Delayed')])
        self.data = link_event(data, self.mid, 'clock_end', 'clock_start')

    def event(self, data, eid):
        return next(row for mission in data['missions']
                    if mission['id'] == self.mid
                    for row in mission['triggers'] if row['id'] == eid)

    def test_ticks_replay_and_condition_edits_preserve_timer(self):
        data = configure_schedule(
            self.data, self.mid, 'clock_end', delay_ticks=2)
        self.assertIn('ATTENDRE 2 ticks',
                      condition_summary(self.event(data, 'clock_end')))
        battle = Battle(Content.from_dict(data), self.mid, seed=7)
        emitted = [(row['id'], row['tick']) for row in battle.events
                   if row['kind'] == 'trigger'
                   and row['id'] in ('clock_start', 'clock_end')]
        self.assertEqual([event_id for event_id, _ in emitted],
                         ['clock_start', 'clock_end'])
        self.assertGreaterEqual(emitted[1][1] - emitted[0][1], 2)
        self.assertEqual(Battle.replay(battle.recording()).digest(),
                         battle.digest())
        modified = update_condition(
            data, self.mid, 'clock_end', condition('tick', tick=0))
        self.assertEqual(self.event(modified, 'clock_end')['delay_ticks'], 2)

    def test_activation_uses_real_journal_and_one_shot(self):
        data = configure_schedule(
            self.data, self.mid, 'clock_end', delay_activations=1)
        battle = Battle(Content.from_dict(data), self.mid, seed=7)
        self.assertNotIn('clock_end', battle.fired)
        self.assertEqual(temporal_status(
            battle, self.event(data, 'clock_end'))['state'], 'ready')
        triggers.dispatch(battle)
        self.assertIn('clock_end', battle.fired)
        before = deepcopy(battle.events)
        triggers.dispatch(battle)
        self.assertEqual(before, battle.events)

    def test_cancel_and_reject_invalid_edits_atomically(self):
        data = save_event(self.data, self.mid, 'clock_cancel',
                          condition('tick', tick=0),
                          [action('message', text='Abort')])
        data = configure_schedule(
            data, self.mid, 'clock_end',
            delay_ticks=50, cancel_after=['clock_cancel'])
        battle = Battle(Content.from_dict(data), self.mid, seed=7)
        self.assertNotIn('clock_end', battle.fired)
        self.assertEqual(temporal_status(
            battle, self.event(data, 'clock_end'))['state'], 'cancelled')
        original = deepcopy(self.data)
        edits = [
            {'delay_ticks': True},
            {'delay_ticks': -2},
            {'delay_activations': 10001},
            {'cancel_after': ['missing']},
            {'cancel_after': ['clock_end']},
        ]
        for kwargs in edits:
            with self.subTest(kwargs=kwargs), self.assertRaises(RuleError):
                configure_schedule(self.data, self.mid, 'clock_end', **kwargs)
            self.assertEqual(self.data, original)
        invalid = deepcopy(self.data)
        self.event(invalid, 'clock_start')['delay_ticks'] = 2
        with self.assertRaises(RuleError):
            Content.from_dict(invalid)

    def test_clear_timing_preserves_existing_dependency_and_actions(self):
        data = configure_schedule(self.data, self.mid, 'clock_end',
                                  delay_ticks=5, delay_activations=2)
        clean = configure_schedule(data, self.mid, 'clock_end',
                                   delay_ticks=0, delay_activations=0)
        after = self.event(clean, 'clock_end')
        self.assertNotIn('delay_ticks', after)
        self.assertNotIn('delay_activations', after)
        self.assertEqual(after['after'], ['clock_start'])
        self.assertEqual(after['actions'],
                         self.event(self.data, 'clock_end')['actions'])


if __name__ == '__main__':
    unittest.main()
