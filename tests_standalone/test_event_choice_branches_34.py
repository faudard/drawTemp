"""3.4: exclusive StoryBook choice branches, OR convergence and genuine replay."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.event_branches import preview_choice_routes, format_choice_routes
from sporebound.event_composer import condition, action, save_event
from sporebound.event_context import condition_trace
from sporebound.event_graph import (
    bind_choice, clear_choice, link_event, link_alternative,
    unlink_alternative, update_condition, chain_descendants, condition_summary)
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.tactical_rpg3 import authored_rules_for_document


class EventChoiceBranchesTests(unittest.TestCase):
    def setUp(self):
        self.raw = Content.load(DEFAULT_CONTENT).to_dict()
        self.mid = 'garden'
        self.data = self.build()
        self.rules = authored_rules_for_document(self.data)
        self.content = Content.from_dict(self.data, rules=self.rules)
        self.project = self.make_project()

    def build(self):
        # Convergence is serialized BEFORE both mutually exclusive branches
        # and before their origin to verify multi-pass dispatcher settlement.
        data = save_event(self.raw, self.mid, 'branch_join',
                          condition('tick', tick=0),
                          [action('message', text='Rendez-vous à la tour')])
        data = save_event(data, self.mid, 'branch_assault',
                          condition('tick', tick=0),
                          [action('hazard', pos=[5, 5], amount=12),
                           action('message', text='Les remparts sont attaqués')])
        data = save_event(data, self.mid, 'branch_truce',
                          condition('tick', tick=0),
                          [action('hazard', pos=[6, 5], amount=3),
                           action('message', text='Trêve négociée')])
        data = save_event(data, self.mid, 'branch_origin',
                          condition('tick', tick=0),
                          [action('message', text='Que faire de la garnison ?')])
        data = link_event(data, self.mid, 'branch_assault', 'branch_origin')
        data = link_event(data, self.mid, 'branch_truce', 'branch_origin')
        data = bind_choice(data, self.mid, 'branch_assault',
                           'garrison_choice', 'fight')
        data = bind_choice(data, self.mid, 'branch_truce',
                           'garrison_choice', 'parley')
        data = link_alternative(data, self.mid, 'branch_join', 'branch_assault')
        data = link_alternative(data, self.mid, 'branch_join', 'branch_truce')
        return data

    def make_project(self):
        raw = GameProject.default(self.content).to_dict()
        raw['story'] = {
            'scenes': [
                {'id': 'garrison_choice', 'title': 'La garnison',
                 'speaker': 'Jeanne', 'text': 'Comment agir ?',
                 'choices': [
                     {'id': 'fight', 'label': 'Attaquer le château',
                      'effects': [{'kind': 'set_flag', 'flag': 'strategy',
                                   'value': 'attack'}],
                      'tactical_effects': [
                          {'kind': 'hazard', 'pos': [4, 5], 'amount': 4}]},
                     {'id': 'parley', 'label': 'Négocier',
                      'effects': [{'kind': 'set_flag', 'flag': 'strategy',
                                   'value': 'peace'}],
                      'tactical_effects': [
                          {'kind': 'open_door', 'object': 'gate'}]},
                ]},
                {'id': 'after_truce', 'title': 'Après le choix',
                 'speaker': 'Jeanne', 'text': 'Avançons.',
                 'choices': [{'id': 'continue', 'label': 'Continuer'}]},
            ],
            'entry_scenes': {}, 'after_mission': {},
            'during_tactical_event': {
                'garden/branch_origin': 'garrison_choice',
                'garden/branch_join': 'after_truce',
            },
        }
        return GameProject.from_dict(raw, self.content)

    def event(self, eid, data=None):
        return next(row for m in (data or self.data)['missions']
                    if m['id'] == self.mid for row in m['triggers']
                    if row['id'] == eid)

    def play(self, choice_id):
        session = GameSession.new(
            self.content, self.project, 'main', rules=self.rules)
        session.start_mission(self.mid)
        self.assertEqual(session.tactical_story_pending, 'garrison_choice')
        self.assertIn('branch_origin', session.active_battle.fired)
        self.assertNotIn('branch_join', session.active_battle.fired)
        session.choose_tactical_story_option(choice_id)
        return session

    def test_real_choice_activates_only_its_branch_and_common_rejoin(self):
        for choice, fired, other, pos, hazard, flag in [
            ('fight', 'branch_assault', 'branch_truce', (5, 5), 12, 'attack'),
            ('parley', 'branch_truce', 'branch_assault', (6, 5), 3, 'peace'),
        ]:
            with self.subTest(choice=choice):
                session = self.play(choice)
                battle = session.active_battle
                self.assertIn(fired, battle.fired)
                self.assertNotIn(other, battle.fired)
                self.assertIn('branch_join', battle.fired)
                self.assertEqual(battle.board.tile(pos).hazard, hazard)
                self.assertEqual(session.progress.story_flags['strategy'], flag)
                self.assertEqual(session.tactical_story_pending, 'after_truce')
                # Canonical replay compares battle digest and GameSession data.
                recorded = session.recording()
                restored = GameSession.from_recording(
                    recorded, self.content, self.project, rules=self.rules)
                self.assertEqual(restored.recording(), recorded)
                self.assertEqual(restored.active_battle.fired, battle.fired)
                self.assertEqual(restored.tactical_story_pending, 'after_truce')
                self.assertEqual(sum(eid == 'branch_join'
                                     for eid in battle.fired), 1)

    def test_each_route_preview_isolated_and_shows_tactical_and_story_effects(self):
        unchanged = deepcopy(self.data)
        orig_project = deepcopy(self.project.to_dict())
        report = preview_choice_routes(
            self.data, self.project, self.mid, 'branch_origin')
        self.assertTrue(report['source_fired'])
        self.assertEqual(report['replay_verified'], None)
        routes = {row['choice_id']: row for row in report['routes']}
        self.assertEqual(set(routes), {'fight', 'parley'})
        self.assertEqual(routes['fight']['fired_ids'],
                         ['branch_assault', 'branch_join'])
        self.assertEqual(routes['parley']['fired_ids'],
                         ['branch_truce', 'branch_join'])
        self.assertEqual(routes['fight']['story_flags']['strategy'], 'attack')
        self.assertEqual(routes['parley']['story_flags']['strategy'], 'peace')
        self.assertIn('NON ATTESTÉ', '\n'.join(format_choice_routes(report)))
        self.assertTrue(any('branch_truce' == x['event_id']
                            for x in routes['fight']['excluded']))
        self.assertEqual(self.data, unchanged)
        self.assertEqual(self.project.to_dict(), orig_project)

    def test_conditions_references_and_undo_are_transactional(self):
        before = deepcopy(self.data)
        self.assertEqual(
            {r['id'] for r in chain_descendants(
                self.data, self.mid, 'branch_origin')},
            {'branch_origin', 'branch_assault', 'branch_truce', 'branch_join'})
        summary = condition_summary(self.event('branch_join'))
        self.assertIn('APRÈS (OU)', summary)
        self.assertIn('CHOIX garrison_choice → fight',
                      condition_summary(self.event('branch_assault')))
        updated = update_condition(self.data, self.mid, 'branch_assault',
                                   condition('tick', tick=3))
        self.assertEqual(self.event('branch_assault', updated)['after_choice'],
                         {'scene': 'garrison_choice', 'choice': 'fight'})
        cleared = clear_choice(updated, self.mid, 'branch_assault')
        self.assertNotIn('after_choice',
                         self.event('branch_assault', cleared))
        unlink = unlink_alternative(self.data, self.mid,
                                    'branch_join', 'branch_truce')
        self.assertEqual(self.event('branch_join', unlink)['after_any'],
                         ['branch_assault'])
        restore = link_alternative(unlink, self.mid, 'branch_join',
                                   'branch_truce')
        self.assertEqual(restore, self.data)
        for mutate in (
            lambda: link_alternative(self.data, self.mid,
                                     'branch_assault', 'branch_join'),
            lambda: link_alternative(self.data, self.mid,
                                     'branch_join', 'branch_assault'),
            lambda: link_alternative(self.data, self.mid,
                                     'branch_assault', 'branch_origin'),
            lambda: bind_choice(self.data, self.mid, 'branch_assault', '', 'x'),
        ):
            with self.assertRaises(RuleError):
                mutate()
            self.assertEqual(self.data, before)

    def test_bad_project_references_and_corrupt_or_links_are_rejected(self):
        before = self.project.to_dict()
        bad = deepcopy(before)
        bad['story']['scenes'][0]['choices'][0]['id'] = 'new_id'
        with self.assertRaises(RuleError):
            GameProject.from_dict(bad, self.content)
        delink = deepcopy(before)
        delink['story']['during_tactical_event'].pop('garden/branch_origin')
        with self.assertRaises(RuleError):
            GameProject.from_dict(delink, self.content)
        for alternatives in ([], ['branch_join'], ['unknown'],
                             ['branch_assault', 'branch_assault']):
            raw = deepcopy(self.data)
            self.event('branch_join', raw)['after_any'] = alternatives
            with self.assertRaises(RuleError):
                Content.from_dict(raw)
        self.assertEqual(self.project.to_dict(), before)

    def test_choice_guards_require_a_validated_linked_story(self):
        with self.assertRaises(RuleError):
            GameProject.default(self.content).validate(self.content)
        raw = deepcopy(self.data)
        self.event('branch_assault', raw)['after_choice'] = {
            'scene': '', 'choice': 'fight'}
        with self.assertRaises(RuleError):
            Content.from_dict(raw)
        self.assertEqual(self.event('branch_assault')['after_choice'],
                         {'scene': 'garrison_choice', 'choice': 'fight'})
        # Public gameplay commands cannot spoof a StoryBook choice.
        session = GameSession.new(
            self.content, self.project, 'main', rules=self.rules)
        session.start_mission(self.mid)
        with self.assertRaises(RuleError):
            session.execute({'kind': 'story_effects',
                             'scene': 'garrison_choice',
                             'choice': 'fight', 'effects': []})

    def test_branch_events_block_without_real_story_choice(self):
        from sporebound.engine import Battle
        battle = Battle(self.content, self.mid, rules=self.rules)
        self.assertFalse(condition_trace(
            battle, self.event('branch_assault'))[0])
        self.assertNotIn('branch_assault', battle.fired)
        self.assertNotIn('branch_join', battle.fired)


if __name__ == '__main__':
    unittest.main()
