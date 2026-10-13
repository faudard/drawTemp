"""3.5B lifecycle gates: expiration, stable cancellation, saved/replayed states."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.event_composer import action, condition, save_event
from sporebound.event_graph import configure_schedule, link_event, condition_summary
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.temporal_events import temporal_snapshot, temporal_status


class DurableTemporalLifecycleTests(unittest.TestCase):
    MID = 'garden'

    def setUp(self):
        raw = Content.load(DEFAULT_CONTENT).to_dict()
        raw = save_event(raw, self.MID, 'alarm',
                         condition('tick', tick=0),
                         [action('message', text='Alarm')])
        raw = save_event(raw, self.MID, 'reinforce',
                         condition('tick', tick=100000),
                         [action('message', text='Arrivals')])
        self.raw = link_event(raw, self.MID, 'reinforce', 'alarm')

    def row(self, data, eid):
        return next(row for mission in data['missions']
                    if mission['id'] == self.MID
                    for row in mission['triggers'] if row['id'] == eid)

    def step_until(self, battle, expected, *, limit=30):
        trigger = next(t for t in battle.mission.triggers
                       if t['id'] == 'reinforce')
        for _ in range(limit):
            current = temporal_status(battle, trigger)['state']
            if current == expected:
                return
            self.assertIsNone(battle.result, 'Combat ended before lifecycle gate')
            self.assertIsNotNone(battle.active, 'Expected a normal CT activation')
            battle.execute({'kind': 'end', 'facing': [0, 1]})
        self.fail('Lifecycle never reached ' + expected)

    def test_expiration_is_terminal_replayed_and_not_fired(self):
        doc = configure_schedule(self.raw, self.MID, 'reinforce',
                                 delay_ticks=1, expire_after_ticks=2)
        battle = Battle(Content.from_dict(doc), self.MID, seed=9)
        first = temporal_status(battle, self.row(doc, 'reinforce'))
        # The constructor advances CT until the first activation, so a
        # short deadline may already have passed before control returns.
        self.assertIn(first['state'], ('scheduled', 'ready', 'expired'))
        self.step_until(battle, 'expired')
        state = deepcopy(battle.state())
        result = next(t for t in state['scheduled_events']
                      if t['id'] == 'reinforce')
        self.assertEqual(result['state'], 'expired')
        self.assertEqual(result['reason'], 'expire_after_ticks')
        self.assertNotIn('reinforce', battle.fired)
        self.assertEqual(temporal_snapshot(battle), state['scheduled_events'])
        self.assertEqual(battle.state(), state)
        rebuilt = Battle.replay(battle.recording())
        self.assertEqual(rebuilt.state()['scheduled_events'],
                         state['scheduled_events'])
        self.assertEqual(rebuilt.digest(), battle.digest())
        for _ in range(3):
            battle.execute({'kind': 'end', 'facing': [0, 1]})
        self.assertEqual(temporal_status(
            battle, self.row(doc, 'reinforce'))['state'], 'expired')

    def test_cancelled_is_terminal_even_after_expiration_deadline(self):
        doc = save_event(self.raw, self.MID, 'disable_alarm',
                         condition('tick', tick=0),
                         [action('message', text='Disabled')])
        doc = configure_schedule(doc, self.MID, 'reinforce',
                                 delay_ticks=2, expire_after_ticks=5,
                                 cancel_after=['disable_alarm'])
        battle = Battle(Content.from_dict(doc), self.MID, seed=7)
        self.assertEqual(temporal_status(
            battle, self.row(doc, 'reinforce'))['state'], 'cancelled')
        # Changing clock time cannot turn a terminal cancellation into expiry.
        battle.tick += 100
        self.assertEqual(temporal_status(
            battle, self.row(doc, 'reinforce'))['state'], 'cancelled')
        self.assertNotIn('reinforce', battle.fired)

    def test_expired_does_not_later_change_to_cancelled(self):
        doc = save_event(self.raw, self.MID, 'disable_alarm',
                         condition('tick', tick=100000),
                         [action('message', text='Disabled')])
        doc = configure_schedule(doc, self.MID, 'reinforce',
                                 delay_ticks=1, expire_after_ticks=2,
                                 cancel_after=['disable_alarm'])
        battle = Battle(Content.from_dict(doc), self.MID, seed=9)
        self.step_until(battle, 'expired')
        battle.emit('trigger', id='disable_alarm')
        battle.fired.append('disable_alarm')
        self.assertEqual(temporal_status(
            battle, self.row(doc, 'reinforce'))['state'], 'expired')

    def test_activation_expiry_and_no_firing_after_deadline(self):
        doc = configure_schedule(
            self.raw, self.MID, 'reinforce',
            expire_after_activations=1)
        battle = Battle(Content.from_dict(doc), self.MID, seed=3)
        # Real initial activation counts toward the duration.
        self.assertEqual(temporal_status(
            battle, self.row(doc, 'reinforce'))['state'], 'expired')
        self.assertNotIn('reinforce', battle.fired)
        self.assertEqual(Battle.replay(battle.recording()).digest(),
                         battle.digest())

    def test_fired_remains_fired_if_cancellation_arrives_later(self):
        doc = save_event(self.raw, self.MID, 'disable_alarm',
                         condition('tick', tick=100000),
                         [action('message', text='Disabled')])
        from sporebound.event_graph import update_condition
        doc = update_condition(doc, self.MID, 'reinforce',
                               condition('tick', tick=0))
        doc = configure_schedule(doc, self.MID, 'reinforce',
                                 cancel_after=['disable_alarm'])
        battle = Battle(Content.from_dict(doc), self.MID, seed=3)
        self.assertIn('reinforce', battle.fired)
        battle.emit('trigger', id='disable_alarm')
        battle.fired.append('disable_alarm')
        self.assertEqual(temporal_status(
            battle, self.row(doc, 'reinforce'))['state'], 'fired')

    def test_session_reload_restores_schedule_without_extra_queue(self):
        doc = configure_schedule(self.raw, self.MID, 'reinforce',
                                 delay_ticks=2, expire_after_ticks=4)
        content = Content.from_dict(doc)
        project = GameProject.default(content)
        session = GameSession.new(content, project, 'main', seed=3)
        session.start_mission(self.MID)
        before = session.active_battle.state()['scheduled_events']
        recording = session.recording()
        restored = GameSession.from_recording(recording, content, project)
        self.assertEqual(restored.recording(), recording)
        self.assertEqual(restored.active_battle.state()['scheduled_events'],
                         before)
        self.assertNotIn('scheduled_events',
                         Battle(Content.load(DEFAULT_CONTENT),
                                self.MID).state())

    def test_expiration_rejects_invalid_windows_atomically(self):
        original = deepcopy(self.raw)
        candidates = [
            {'expire_after_ticks': True},
            {'expire_after_ticks': -1},
            {'expire_after_activations': 10001},
            {'delay_ticks': 5, 'expire_after_ticks': 5},
            {'delay_activations': 5, 'expire_after_activations': 4},
        ]
        for args in candidates:
            with self.subTest(args=args), self.assertRaises(RuleError):
                configure_schedule(self.raw, self.MID, 'reinforce', **args)
            self.assertEqual(self.raw, original)
        valid = configure_schedule(
            self.raw, self.MID, 'reinforce', expire_after_ticks=10)
        self.assertIn('EXPIRE À 10 ticks',
                      condition_summary(self.row(valid, 'reinforce')))
        cleared = configure_schedule(
            valid, self.MID, 'reinforce', expire_after_ticks=0)
        self.assertNotIn('expire_after_ticks', self.row(cleared, 'reinforce'))
        self.assertEqual(self.row(cleared, 'reinforce')['actions'],
                         self.row(self.raw, 'reinforce')['actions'])


if __name__ == '__main__':
    unittest.main()
