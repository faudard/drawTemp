"""3.3: deterministic, read-only event debugger using the live trigger dispatcher."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.entity_event_studio import author_gate_sequence
from sporebound.event_composer import action, condition, save_event
from sporebound.event_context import preview_event_chain
from sporebound.event_debugger import EventDebugger, format_debug_report
from sporebound.event_graph import link_event
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.rules import triggers
from sporebound.tactical_rpg3 import authored_rules_for_document


class EventDebuggerTests(unittest.TestCase):
    def setUp(self):
        self.raw = Content.load(DEFAULT_CONTENT).to_dict()
        self.mid = 'garden'
        self.data = self.make_reverse_chain()

    def make_reverse_chain(self):
        # Reverse authoring order exercises the actual multi-pass dispatcher.
        data = save_event(self.raw, self.mid, 'debug_last',
                          condition('tick', tick=0),
                          [action('hazard', pos=[5, 5], amount=12)])
        data = save_event(data, self.mid, 'debug_middle',
                          condition('tick', tick=0),
                          [action('hazard', pos=[4, 5], amount=6)])
        data = save_event(data, self.mid, 'debug_first',
                          condition('tick', tick=0),
                          [action('message', text='Signal')])
        data = link_event(data, self.mid, 'debug_middle', 'debug_first')
        data = link_event(data, self.mid, 'debug_last', 'debug_middle')
        return data

    def test_step_by_step_matches_real_uninterrupted_dispatch(self):
        baseline = deepcopy(self.data)
        debug = EventDebugger(self.data, self.mid, 'debug_first')
        self.assertEqual(debug.report()['timeline'], [])
        self.assertEqual(debug.inspect('debug_middle')['passed'], False)
        for index, eid in enumerate(('debug_first', 'debug_middle', 'debug_last'), 1):
            report = debug.step()
            self.assertEqual(report['fired_ids'][-1], eid)
            self.assertEqual(len(report['timeline']), index)
            self.assertEqual(report['timeline'][-1]['event_id'], eid)
        self.assertTrue(report['exhausted'])
        self.assertEqual(debug.battle.board.tile((4, 5)).hazard, 6)
        self.assertEqual(debug.battle.board.tile((5, 5)).hazard, 12)
        self.assertEqual(report['replay_verified'], None)
        self.assertTrue(report['isolated'])
        self.assertIn('Replay : NON ATTESTÉ', '\n'.join(format_debug_report(report)))
        expected = preview_event_chain(self.data, self.mid, 'debug_first',
                                       include_scene=True)
        self.assertEqual(expected['fired_ids'], report['fired_ids'])
        self.assertEqual(expected['scene_after'].board.tile((5, 5)).hazard,
                         debug.battle.board.tile((5, 5)).hazard)
        self.assertEqual(self.data, baseline)

    def test_break_before_effect_then_continue_bypasses_once(self):
        debug = EventDebugger(self.data, self.mid, 'debug_first')
        debug.set_breakpoint('debug_middle')
        paused = debug.continue_to_breakpoint()
        self.assertEqual(paused['paused_on'], 'debug_middle')
        self.assertEqual(paused['fired_ids'], ['debug_first'])
        self.assertEqual(debug.battle.board.tile((4, 5)).hazard, 0)
        self.assertEqual(len(paused['timeline']), 1)
        resumed = debug.continue_to_breakpoint()
        self.assertEqual(resumed['paused_on'], None)
        self.assertEqual(resumed['fired_ids'],
                         ['debug_first', 'debug_middle', 'debug_last'])
        self.assertEqual(len(resumed['timeline']), 3)
        self.assertEqual(resumed['timeline'][1]['changes'],
                         ['Case (4, 5) · danger : 0 → 6'])
        self.assertEqual(len(set(resumed['fired_ids'])), 3)

    def test_multiple_breakpoints_and_manual_step(self):
        debug = EventDebugger(self.data, self.mid, 'debug_first')
        debug.set_breakpoint('debug_middle')
        debug.set_breakpoint('debug_last')
        self.assertEqual(debug.continue_to_breakpoint()['paused_on'],
                         'debug_middle')
        self.assertEqual(debug.step()['fired_ids'],
                         ['debug_first', 'debug_middle'])
        self.assertEqual(debug.continue_to_breakpoint()['paused_on'],
                         'debug_last')
        self.assertEqual(debug.step()['fired_ids'],
                         ['debug_first', 'debug_middle', 'debug_last'])
        self.assertTrue(debug.step()['exhausted'])

    def test_invalid_breakpoints_and_stalled_condition_are_explicit(self):
        debug = EventDebugger(self.data, self.mid, 'debug_last')
        with self.assertRaises(RuleError):
            debug.set_breakpoint('missing')
        with self.assertRaises(RuleError):
            debug.set_breakpoint('debug_last', 'on')
        stalled = debug.continue_to_breakpoint()
        self.assertTrue(stalled['exhausted'])
        self.assertEqual(stalled['fired_ids'], [])
        self.assertIn({'event_id': 'debug_last', 'reason': 'prerequisite',
                       'missing': ['debug_middle']}, stalled['waiting'])
        self.assertFalse(debug.inspect('debug_last')['passed'])

    def test_interaction_is_real_battle_command_and_not_a_fake_trigger(self):
        project = GameProject.default(Content.from_dict(self.raw))
        data, project = author_gate_sequence(
            self.raw, project, self.mid, door_id='gate',
            lever_id='switch', lever_cell=[2, 4],
            event_id='debug_gate', danger_cell=[5, 5], danger=8)
        data = save_event(data, self.mid, 'debug_alarm',
                          condition('tick', tick=0),
                          [action('message', text='Alerte')])
        data = link_event(data, self.mid, 'debug_alarm', 'debug_gate')
        debug = EventDebugger(data, self.mid, 'debug_gate',
                              project=project, scenario='satisfied')
        self.assertNotIn('debug_gate', debug.battle.fired)
        self.assertFalse(debug.battle.board.tile((4, 1)).blocked)
        first = debug.step()
        self.assertEqual(first['fired_ids'], ['debug_gate'])
        final = debug.step()
        self.assertEqual(final['fired_ids'], ['debug_gate', 'debug_alarm'])
        self.assertEqual(final['cinematic_ids'], ['cin_debug_gate'])
        self.assertEqual(debug.battle.board.tile((5, 5)).hazard, 8)
        self.assertTrue(any(c['kind'] == 'interact' for c in
                            debug.battle.events))
        self.assertEqual(final['replay_verified'], None)

    def test_false_composite_is_reported_without_activating_effects(self):
        from sporebound.event_graph import extend_condition
        data = save_event(
            self.raw, self.mid, 'debug_blocked',
            condition('tick', tick=0),
            [action('hazard', pos=[4, 5], amount=44)])
        data = extend_condition(
            data, self.mid, 'debug_blocked',
            condition('tick', tick=100))
        debug = EventDebugger(data, self.mid, 'debug_blocked',
                              scenario='initial')
        result = debug.step()
        self.assertTrue(result['exhausted'])
        self.assertFalse(result['fired_ids'])
        self.assertEqual(result['latest_conditions']['debug_blocked']['state'],
                         'composite_false')
        details = debug.inspect('debug_blocked')
        self.assertFalse(details['passed'])
        self.assertEqual([r['passed'] for r in details['conditions']],
                         [True, False])
        self.assertNotEqual(debug.battle.board.tile((4, 5)).hazard, 44)

    def test_opt_in_observer_has_identical_runtime_result(self):
        raw = save_event(
            self.raw, self.mid, 'debug_observe',
            condition('tick', tick=100),
            [action('hazard', pos=[4, 5], amount=16)])
        content = Content.from_dict(raw)
        battle = Battle(content, self.mid)
        clone = deepcopy(battle)
        battle.tick = clone.tick = 100
        observations = []
        outcome = triggers.dispatch(
            battle, observer=observations.append,
            before_fire=lambda _row: False)
        triggers.dispatch(clone)
        # Garden also has a legacy tick-20 spore_pulse at tick 100.
        # Observed dispatch must match all ready canonical triggers, not
        # assume our newly authored trigger is the only one.
        self.assertEqual(outcome['fired'], 2)
        self.assertEqual([row['event_id'] for row in observations
                          if row['state'] == 'fired'],
                         ['spore_pulse', 'debug_observe'])
        self.assertEqual(battle.digest(), clone.digest())

    def test_failing_action_rolls_back_disposable_debug_step(self):
        # Existing validation intentionally permits a despawn-by-ID whose
        # target may not be present when the trigger actually fires.
        raw = save_event(
            self.raw, self.mid, 'debug_fail',
            condition('tick', tick=0),
            [action('message', text='Avant échec'),
             action('despawn', unit='missing_runtime_unit')])
        debug = EventDebugger(raw, self.mid, 'debug_fail')
        before = deepcopy(debug.battle.state())
        with self.assertRaises(RuleError):
            debug.step()
        self.assertEqual(debug.battle.state(), before)
        self.assertEqual(debug.timeline, [])
        self.assertNotIn('debug_fail', debug.battle.fired)
        self.assertFalse(debug.exhausted)

    def test_player_replay_stays_strict_and_dispatch_rejects_invalid_limit(self):
        rules = authored_rules_for_document(self.data)
        content = Content.from_dict(self.data, rules=rules)
        project = GameProject.default(content)
        session = GameSession.new(content, project, 'main', rules=rules)
        session.start_mission(self.mid)
        recorded = session.recording()
        self.assertEqual(recorded, GameSession.from_recording(
            recorded, content, project, rules=rules).recording())
        self.assertEqual([x for x in session.active_battle.fired
                          if x.startswith('debug_')],
                         ['debug_first', 'debug_middle', 'debug_last'])
        with self.assertRaises(RuleError):
            triggers.dispatch(session.active_battle, fire_limit=0)
        # Regular Battle never gets debug-only snapshot or breakpoint state.
        self.assertFalse(hasattr(session.active_battle, 'event_debugger'))


if __name__ == '__main__':
    unittest.main()
