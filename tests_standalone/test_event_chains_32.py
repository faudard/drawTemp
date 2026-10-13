"""3.2: genuine one-shot trigger cascades, authoring and Player replay."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.cinematics import cinematic_template, tactical_event_target
from sporebound.entity_event_studio import author_gate_sequence
from sporebound.event_composer import action, condition, save_event
from sporebound.event_context import (
    preview_event_chain, format_chain_report, preview_event)
from sporebound.event_graph import (
    link_event, unlink_event, chain_descendants, build_event_graph,
    condition_summary, update_condition, reorder_event)
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.story_authoring import create_scene, set_tactical_scene
from sporebound.tactical_rpg3 import authored_rules_for_document


class ChainedTacticalEventTests(unittest.TestCase):
    def setUp(self):
        self.raw = Content.load(DEFAULT_CONTENT).to_dict()
        self.mid = 'garden'
        self.data = self.build_chain()
        self.rules = authored_rules_for_document(self.data)

    def build_chain(self):
        # Deliberately reverse authoring order: the downstream effect must
        # settle on the SAME engine command boundary as the first trigger.
        data = save_event(self.raw, self.mid, 'chain_final',
                          condition('tick', tick=0),
                          [action('hazard', pos=(5, 5), amount=9),
                           action('message', text='La tour est alertee')])
        data = save_event(data, self.mid, 'chain_middle',
                          condition('tick', tick=0),
                          [action('hazard', pos=(4, 5), amount=6)])
        data = save_event(data, self.mid, 'chain_start',
                          condition('tick', tick=0),
                          [action('message', text='Le signal est donne')])
        data = link_event(data, self.mid, 'chain_middle', 'chain_start')
        data = link_event(data, self.mid, 'chain_final', 'chain_middle')
        return data

    def event(self, data, eid):
        return next(e for m in data['missions'] if m['id'] == self.mid
                    for e in m.get('triggers', []) if e['id'] == eid)

    def test_dependency_graph_is_bounded_atomic_and_preserves_content(self):
        previous = deepcopy(self.data)
        bad = [
            lambda: link_event(self.data, self.mid, 'chain_start', 'chain_final'),
            lambda: link_event(self.data, self.mid, 'chain_start', 'chain_start'),
            lambda: link_event(self.data, self.mid, 'chain_final', 'missing'),
            lambda: link_event(self.data, self.mid, 'chain_middle', 'chain_start'),
            lambda: unlink_event(self.data, self.mid, 'chain_final', 'chain_start'),
        ]
        for change in bad:
            with self.subTest(operation=change), self.assertRaises(RuleError):
                change()
            self.assertEqual(self.data, previous)
        self.assertEqual(self.event(self.data, 'chain_final')['after'],
                         ['chain_middle'])
        self.assertIn('APRÈS chain_middle',
                      condition_summary(self.event(self.data, 'chain_final')))
        graph = build_event_graph(self.data, self.mid)
        self.assertIn({'source': ('chain_middle', 'action', 0),
                       'target': ('chain_final', 'condition'),
                       'event_id': 'chain_final', 'label': 'après événement'},
                      graph['edges'])
        self.assertEqual([r['id'] for r in
                          chain_descendants(self.data, self.mid, 'chain_start')],
                         ['chain_final', 'chain_middle', 'chain_start'])
        changed = unlink_event(self.data, self.mid, 'chain_final',
                               'chain_middle')
        self.assertNotIn('after', self.event(changed, 'chain_final'))
        restored = link_event(changed, self.mid, 'chain_final',
                              'chain_middle')
        self.assertEqual(restored, self.data)
        updated = update_condition(self.data, self.mid, 'chain_final',
                                   condition('tick', tick=0))
        self.assertEqual(self.event(updated, 'chain_final')['after'],
                         ['chain_middle'])

    def test_validation_rejects_corrupted_records_and_cycles_on_load(self):
        original = deepcopy(self.data)
        for after in [[], ['chain_final'], ['unknown'],
                      ['chain_middle', 'chain_middle'],
                      list(range(9))]:
            corrupt = deepcopy(self.data)
            self.event(corrupt, 'chain_final')['after'] = after
            with self.subTest(after=after), self.assertRaises(RuleError):
                Content.from_dict(corrupt)
            self.assertEqual(self.data, original)

    def test_real_cascade_preview_multiple_tiles_without_fake_proofs(self):
        data_before = deepcopy(self.data)
        report = preview_event_chain(
            self.data, self.mid, 'chain_start',
            scenario='satisfied', include_scene=True)
        self.assertEqual(report['fired_ids'],
                         ['chain_start', 'chain_middle', 'chain_final'])
        self.assertFalse(report['error'])
        self.assertFalse(report['waiting'])
        self.assertEqual(report['scene_after'].board.tile((4, 5)).hazard, 6)
        self.assertEqual(report['scene_after'].board.tile((5, 5)).hazard, 9)
        self.assertEqual(report['replay_verified'], None)
        self.assertIn('Replay : non attesté',
                      '\n'.join(format_chain_report(report)))
        self.assertEqual(self.data, data_before)
        denied = preview_event_chain(self.data, self.mid, 'chain_final')
        self.assertNotIn('chain_final', denied['fired_ids'])
        self.assertEqual(denied['waiting'][0],
                         {'event_id': 'chain_final',
                          'missing': ['chain_middle']})
        # A standalone preview must not pretend an isolated downstream trigger
        # can satisfy its upstream proof.
        individual = preview_event(self.data, self.mid, 'chain_final',
                                   scenario='satisfied')
        self.assertFalse(individual['fired'])
        self.assertFalse(individual['condition_passed'])

    def test_actual_session_executes_chain_once_and_replay_restores_it(self):
        content = Content.from_dict(self.data, rules=self.rules)
        project = GameProject.default(content)
        session = GameSession.new(content, project, 'main', rules=self.rules)
        session.start_mission(self.mid)
        battle = session.active_battle
        triggered = [row['id'] for row in battle.events
                     if row['kind'] == 'trigger' and
                     row['id'].startswith('chain_')]
        self.assertEqual(triggered,
                         ['chain_start', 'chain_middle', 'chain_final'])
        self.assertEqual(battle.board.tile((4, 5)).hazard, 6)
        self.assertEqual(battle.board.tile((5, 5)).hazard, 9)
        saved = session.recording()   # internally authenticates Battle.replay
        loaded = GameSession.from_recording(
            saved, content, project, rules=self.rules)
        self.assertEqual(saved, loaded.recording())
        self.assertEqual(
            [eid for eid in loaded.active_battle.fired if eid.startswith('chain_')],
            ['chain_start', 'chain_middle', 'chain_final'])

    def test_chain_does_not_double_fire_with_extra_dispatch(self):
        from sporebound.rules import triggers
        content = Content.from_dict(self.data, rules=self.rules)
        from sporebound.engine import Battle
        battle = Battle(content, self.mid, rules=self.rules)
        before = deepcopy(battle.events)
        triggers.dispatch(battle)
        triggers.dispatch(battle)
        self.assertEqual(battle.events, before)
        self.assertEqual(sum(x == 'chain_final' for x in battle.fired), 1)

    def test_real_gate_interaction_activates_immediate_downstream_effect(self):
        project = GameProject.default(Content.from_dict(self.raw))
        data, project = author_gate_sequence(
            self.raw, project, self.mid,
            door_id='gate', lever_id='switch', lever_cell=[2, 4],
            event_id='open_gate_chain', danger_cell=[5, 5],
            danger=4, dialogue='Le signal est donné')
        data = save_event(
            data, self.mid, 'reinforcements_alert',
            condition('tick', tick=0),
            [action('hazard', pos=[3, 5], amount=11),
             action('message', text='Les gardes sont alertés')])
        data = link_event(data, self.mid,
                          'reinforcements_alert', 'open_gate_chain')
        rules = authored_rules_for_document(data)
        content = Content.from_dict(data, rules=rules)
        session = GameSession.new(content, project, 'main', rules=rules)
        session.start_mission(self.mid)
        battle = session.active_battle
        self.assertNotIn('reinforcements_alert', battle.fired)
        actor = battle.unit('momo')
        battle.active_id = actor.id
        actor.ct = 100
        actor.acted = False
        # Same public command boundary as the Player, not a forged trigger.
        session.execute({'kind': 'interact', 'unit': actor.id,
                         'object': 'switch'})
        self.assertEqual([x for x in battle.fired if x in (
            'open_gate_chain', 'reinforcements_alert')],
                         ['open_gate_chain', 'reinforcements_alert'])
        self.assertFalse(battle.board.tile((4, 1)).blocked)
        self.assertEqual(battle.board.tile((3, 5)).hazard, 11)

    def test_scene_and_cinematic_tied_to_real_cascade_event(self):
        content = Content.from_dict(self.data, rules=self.rules)
        project = GameProject.default(content)
        project = create_scene(project, content, 'chain_dialogue',
                               'Le message', 'Les soldats arrivent', 'Jeanne')
        project = set_tactical_scene(
            project, content, self.mid, 'chain_final', 'chain_dialogue')
        data = project.to_dict()
        clip = cinematic_template(
            'cin_chain_final', 'Assaut de la tour', 'tactical_event',
            tactical_event_target(self.mid, 'chain_final'))
        data.setdefault('cinematics', []).append(clip)
        project = GameProject.from_dict(data, content)
        report = preview_event_chain(self.data, self.mid,
                                     'chain_start', project=project)
        self.assertEqual(report['cinematic_ids'], ['cin_chain_final'])
        self.assertEqual(report['narrative_scene_ids'], ['chain_dialogue'])
        session = GameSession.new(content, project, 'main', rules=self.rules)
        session.start_mission(self.mid)
        self.assertIn('chain_final', session.active_battle.fired)
        self.assertEqual(session.tactical_story_pending, 'chain_dialogue')
        journal = session.recording()
        loaded = GameSession.from_recording(
            journal, content, project, rules=self.rules)
        self.assertEqual(loaded.tactical_story_pending, 'chain_dialogue')


if __name__ == '__main__':
    unittest.main()
