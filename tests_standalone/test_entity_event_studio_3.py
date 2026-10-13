"""Entity & Event Studio 3.0: bounded composite gates, ordered actions, Player hooks."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.cinematics import triggered_tactical_cinematics
from sporebound.entity_event_studio import author_gate_sequence, probe_gate_sequence
from sporebound.event_composer import action, condition, save_event
from sporebound.event_context import preview_event
from sporebound.event_graph import (
    extend_condition, clear_composite_condition, condition_summary, add_action,
    reorder_action)
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.tactical_rpg3 import authored_rules_for_document


class EntityEventStudio3Tests(unittest.TestCase):
    def setUp(self):
        self.raw = Content.load(DEFAULT_CONTENT).to_dict()
        self.project = GameProject.default(Content.from_dict(self.raw))
        self.mid = 'garden'

    def author(self, **kwargs):
        options = dict(door_id='gate', lever_id='switch', lever_cell=[2, 4],
                       event_id='gate_alarm_3', danger_cell=[5, 5],
                       danger=7, dialogue='La porte est ouverte')
        options.update(kwargs)
        return author_gate_sequence(self.raw, self.project, self.mid, **options)

    def test_composite_and_or_not_preview_player_and_ordered_effects(self):
        before = deepcopy(self.raw)
        data, project = self.author()
        data = extend_condition(data, self.mid, 'gate_alarm_3',
                                condition('tick', tick=0))
        data = extend_condition(data, self.mid, 'gate_alarm_3',
                                condition('wave_capacity', max_alive=100),
                                join='any')
        data = extend_condition(data, self.mid, 'gate_alarm_3',
                                condition('tick', tick=99), negate=True)
        data = add_action(data, self.mid, 'gate_alarm_3',
                          action('message', text='Renforts alertés'))
        data = reorder_action(data, self.mid, 'gate_alarm_3', 2, -1)
        event = next(e for e in Content.from_dict(data).missions[self.mid].triggers
                     if e['id'] == 'gate_alarm_3')
        self.assertEqual(event['condition'], 'interact')
        self.assertEqual([a['kind'] for a in event['actions']],
                         ['message', 'message', 'hazard'])
        self.assertIn('OU', condition_summary(event))
        self.assertIn('NON', condition_summary(event))
        self.assertEqual(event['when']['all'][0]['any'][0]['value'], 0)
        self.assertEqual(event['when']['all'][1]['not']['value'], 99)

        report = probe_gate_sequence(data, project, self.mid,
                                     'gate_alarm_3', 'gate')
        self.assertTrue(report['gate_scenario_ok'], report['event']['error'])
        self.assertEqual(report['cinematic_ids'], ['cin_gate_alarm_3'])
        self.assertEqual(report['event']['outcome'], 'applied')
        self.assertEqual(report['event']['scene_after'].board.tile((5, 5)).hazard, 7)
        self.assertEqual([a for a in report['event']['actions'] if a.startswith('Message')],
                         ['Message : La porte est ouverte', 'Message : Renforts alertés'])
        clips, acknowledged = triggered_tactical_cinematics(
            project, report['event']['scene_after'])
        self.assertEqual([clip['id'] for clip in clips], ['cin_gate_alarm_3'])
        again, _ = triggered_tactical_cinematics(
            project, report['event']['scene_after'], acknowledged)
        self.assertFalse(again)
        inactive = preview_event(data, self.mid, 'gate_alarm_3',
                                 scenario='unsatisfied')
        self.assertFalse(inactive['fired'])
        self.assertEqual(self.raw, before)
        self.assertEqual(Content.from_dict(data).to_dict(), data)

    def test_guided_minimum_tick_and_multiple_actions(self):
        data, project = self.author(
            min_tick=3, extra_actions=[action('message', text='Seconde alerte')])
        event = next(e for e in Content.from_dict(data).missions[self.mid].triggers
                     if e['id'] == 'gate_alarm_3')
        self.assertEqual(event['when'], condition('tick', tick=3))
        self.assertEqual(len(event['actions']), 3)
        report = probe_gate_sequence(data, project, self.mid,
                                     'gate_alarm_3', 'gate')
        self.assertTrue(report['gate_scenario_ok'], report['event']['error'])
        self.assertEqual(report['event']['tick'], 3)
        self.assertIn('gate_alarm_3', report['event']['scene_after'].fired)

    def test_false_secondary_condition_blocks_effect_and_cinematic(self):
        data, project = self.author(min_tick=100)
        content = Content.from_dict(data, rules=authored_rules_for_document(data))
        session = GameSession.new(content, project, 'main')
        session.start_mission(self.mid)
        battle = session.active_battle
        actor = battle.unit('momo')
        battle.active_id = actor.id
        actor.ct = 100
        actor.acted = False
        session.execute({'kind': 'interact', 'unit': 'momo', 'object': 'switch'})
        self.assertNotIn('gate_alarm_3', battle.fired)
        self.assertNotEqual(battle.board.tile((5, 5)).hazard, 7)
        clips, _ = triggered_tactical_cinematics(project, battle)
        self.assertFalse(clips)

    def test_composite_bounds_and_invalid_leaves_are_atomic(self):
        data, project = self.author()
        original = deepcopy(data)
        cases = [
            lambda: extend_condition(data, self.mid, 'gate_alarm_3',
                                     {'condition': 'unknown'}),
            lambda: extend_condition(data, self.mid, 'gate_alarm_3',
                                     condition('defeated', unit='missing')),
            lambda: extend_condition(data, self.mid, 'gate_alarm_3',
                                     condition('tick', tick=-1)),
        ]
        for fn in cases:
            with self.subTest(fn=fn), self.assertRaises(RuleError):
                fn()
            self.assertEqual(data, original)
        invalid = deepcopy(data)
        event = next(e for e in invalid['missions'][0]['triggers']
                     if e['id'] == 'gate_alarm_3') if any(
                         e['id'] == 'gate_alarm_3' for e in invalid['missions'][0]['triggers']
                     ) else next(e for m in invalid['missions'] if m['id'] == self.mid
                                 for e in m['triggers'] if e['id'] == 'gate_alarm_3')
        event['when'] = {'all': []}
        with self.assertRaises(RuleError):
            Content.from_dict(invalid)
        event['when'] = {'not': {'not': {'not': {'not': condition('tick', tick=0)}}}}
        with self.assertRaises(RuleError):
            Content.from_dict(invalid)
        cleared = clear_composite_condition(
            extend_condition(data, self.mid, 'gate_alarm_3',
                             condition('tick', tick=2)), self.mid, 'gate_alarm_3')
        self.assertEqual(cleared, original)
        self.assertEqual(project.cinematics[0]['id'], 'cin_gate_alarm_3')

    def test_serialized_session_replays_canonical_composite_content(self):
        # Verify GameSession's real authenticated recording is compatible with
        # composite-authored missions, without fabricating a battle activation.
        data, project = self.author(min_tick=2)
        content = Content.from_dict(data, rules=authored_rules_for_document(data))
        session = GameSession.new(content, project, 'main')
        session.start_mission(self.mid)
        recorded = session.recording()
        resumed = GameSession.from_recording(
            recorded, content, project, rules=authored_rules_for_document(data))
        self.assertEqual(recorded, resumed.recording())


if __name__ == '__main__':
    unittest.main()
