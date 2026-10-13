"""Entity & Event Studio 2.0 regression and end-to-end siege gate."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.cinematics import (tactical_event_target,
                                   triggered_tactical_cinematics)
from sporebound.engine import Battle
from sporebound.entity_event_studio import (author_gate_sequence,
                                             gate_context, probe_gate_sequence)
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.tactical_rpg3 import authored_rules_for_document


class EntityEventStudioTests(unittest.TestCase):
    def setUp(self):
        self.raw = Content.load(DEFAULT_CONTENT).to_dict()
        self.project = GameProject.default(Content.from_dict(self.raw))
        self.mid = 'garden'

    def compose(self, **kwargs):
        options = dict(
            door_id='gate', lever_id='switch', lever_cell=[2, 4],
            event_id='gate_alarm', danger_cell=[5, 5], danger=7,
            dialogue='Les remparts sont ouverts !')
        options.update(kwargs)
        return author_gate_sequence(
            self.raw, self.project, self.mid, **options)

    def test_existing_gate_lever_trigger_cinematic_validate_and_roundtrip(self):
        initial_raw, initial_project = deepcopy(self.raw), deepcopy(self.project.to_dict())
        door, levers = gate_context(self.raw, self.mid, 'gate')
        self.assertEqual(door['kind'], 'door')
        self.assertEqual([row['id'] for row in levers], ['switch'])
        data, project = self.compose()
        mission = next(m for m in data['missions'] if m['id'] == self.mid)
        self.assertEqual(len(mission['objects']), len(
            next(m for m in self.raw['missions'] if m['id'] == self.mid)['objects']))
        event = next(e for e in mission['triggers'] if e['id'] == 'gate_alarm')
        self.assertEqual(event['condition'], 'interact')
        self.assertEqual(event['object'], 'switch')
        self.assertEqual([a['kind'] for a in event['actions']],
                         ['message', 'hazard'])
        self.assertEqual(event['actions'][1]['pos'], [5, 5])
        self.assertEqual(project.cinematics[-1]['trigger'], {
            'kind': 'tactical_event',
            'target': tactical_event_target(self.mid, 'gate_alarm')})
        content = Content.from_dict(data, rules=authored_rules_for_document(data))
        self.assertEqual(Content.from_dict(content.to_dict(),
                         rules=authored_rules_for_document(data)).to_dict(), data)
        self.assertEqual(GameProject.from_dict(project.to_dict(), content).to_dict(),
                         project.to_dict())
        self.assertEqual(self.raw, initial_raw)
        self.assertEqual(self.project.to_dict(), initial_project)

    def test_real_engine_preview_changes_gate_hazard_and_player_movie_queue(self):
        data, project = self.compose()
        report = probe_gate_sequence(
            data, project, self.mid, 'gate_alarm', 'gate')
        self.assertTrue(report['gate_scenario_ok'])
        self.assertTrue(report['gate_opened'])
        self.assertTrue(report['gate_passable'])
        self.assertTrue(report['tactical_effect'])
        self.assertEqual(report['cinematic_ids'], ['cin_gate_alarm'])
        battle = report['event']['scene_after']
        self.assertIsInstance(battle, Battle)
        self.assertEqual(battle.board.tile((5, 5)).hazard, 7)
        self.assertIn('gate_alarm', battle.fired)
        clips, acknowledged = triggered_tactical_cinematics(project, battle)
        self.assertEqual([c['id'] for c in clips], ['cin_gate_alarm'])
        clips_again, _ = triggered_tactical_cinematics(
            project, battle, acknowledged)
        self.assertEqual(clips_again, [])
        self.assertTrue(any('Objet gate · open' in line
                            for line in report['event']['changes']))

    def test_immediate_player_session_interaction_dispatches_event(self):
        data, project = self.compose()
        content = Content.from_dict(data, rules=authored_rules_for_document(data))
        session = GameSession.new(content, project, 'main')
        session.start_mission(self.mid)
        battle = session.active_battle
        # Arrange only the current activation; execute through the public
        # GameSession/Battle command boundary, not a mock event dispatcher.
        actor = battle.unit('momo')
        battle.active_id = actor.id
        actor.ct = 100
        actor.acted = False
        session.execute({'kind': 'interact', 'unit': 'momo', 'object': 'switch'})
        self.assertIn('gate_alarm', battle.fired)
        self.assertEqual(battle.board.tile((5, 5)).hazard, 7)
        self.assertFalse(battle.board.tile((4, 1)).blocked)
        clips, _ = triggered_tactical_cinematics(project, battle)
        self.assertEqual([row['id'] for row in clips], ['cin_gate_alarm'])
        # Repeated checks must not fire the one-shot trigger twice.
        count = sum(row['kind'] == 'trigger' and row.get('id') == 'gate_alarm'
                    for row in battle.events)
        session.execute({'kind': 'end', 'unit': 'momo'})
        self.assertEqual(count, 1)
        self.assertEqual(sum(row['kind'] == 'trigger'
                             and row.get('id') == 'gate_alarm'
                             for row in battle.events), 1)

    def test_new_lever_is_created_with_existing_object_contract(self):
        data, project = self.compose(
            lever_id='lever_new', lever_cell=[3, 4], event_id='new_gate')
        mission = next(m for m in data['missions'] if m['id'] == self.mid)
        new_lever = next(o for o in mission['objects'] if o['id'] == 'lever_new')
        self.assertEqual(new_lever['link'], 'gate')
        self.assertEqual(new_lever['pos'], [3, 4])
        self.assertTrue(probe_gate_sequence(
            data, project, self.mid, 'new_gate', 'gate')['gate_scenario_ok'])

    def test_invalid_link_ids_and_out_of_bounds_are_atomic(self):
        original_data = deepcopy(self.raw)
        original_project = deepcopy(self.project.to_dict())
        invalid = [
            dict(door_id='missing'),
            dict(lever_id='chest', lever_cell=[2, 0]),
            dict(lever_id='switch', lever_cell=[2, 3]),
            dict(lever_id='other', lever_cell=[4, 1]),
            dict(lever_id='other', lever_cell=[100, 100]),
            dict(event_id='spore_pulse'),
            dict(danger_cell=[-1, 4]),
            dict(danger=0),
            dict(dialogue=''),
        ]
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(RuleError):
                self.compose(**options)
        self.assertEqual(self.raw, original_data)
        self.assertEqual(self.project.to_dict(), original_project)

    def test_save_reload_and_content_referential_integrity(self):
        data, project = self.compose()
        content = Content.from_dict(data, rules=authored_rules_for_document(data))
        restored = GameProject.from_dict(project.to_dict(), content)
        self.assertEqual(restored.cinematics[0]['events'][1]['text'],
                         'Les remparts sont ouverts !')
        tampered = deepcopy(data)
        next(m for m in tampered['missions'] if m['id'] == self.mid)[
            'triggers'] = [e for e in next(m for m in tampered['missions']
                                          if m['id'] == self.mid)['triggers']
                          if e['id'] != 'gate_alarm']
        # A persisted project cannot silently reference a deleted trigger.
        with self.assertRaises(RuleError):
            GameProject.from_dict(restored.to_dict(), Content.from_dict(tampered))


if __name__ == '__main__':
    unittest.main()
