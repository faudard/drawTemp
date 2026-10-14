"""3.6: canonical visual Story/Event ports, constraints, history and replay."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.event_composer import action, condition, save_event
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.studio_transaction import StudioHistory
from sporebound.tactical_rpg3 import authored_rules_for_document
from sporebound.visual_branch_graph import (
    connect_visual_branch, visual_target_palette)


class VisualBranchGraphTests(unittest.TestCase):
    def setUp(self):
        raw = Content.load(DEFAULT_CONTENT).to_dict()
        for eid, text in (
                ('v36_join', 'Le groupe se retrouve'),
                ('v36_assault', 'Assaut'),
                ('v36_parley', 'Pourparlers'),
                ('v36_origin', 'Que décidez-vous ?')):
            raw = save_event(raw, 'garden', eid, condition('tick', tick=0),
                             [action('message', text=text)])
        content = Content.from_dict(raw)
        project_raw = GameProject.default(content).to_dict()
        project_raw['story'] = {
            'scenes': [
                {'id': 'v36_dialogue', 'title': 'À la porte',
                 'speaker': 'Jeanne', 'text': 'Quelle approche ?',
                 'choices': [
                     {'id': 'assault', 'label': 'Assaillir'},
                     {'id': 'parley', 'label': 'Négocier'},
                     {'id': 'wait', 'label': 'Attendre'},
                 ]},
                {'id': 'v36_assault_scene', 'title': 'Assaut',
                 'speaker': 'Jeanne', 'text': 'On attaque.',
                 'choices': [{'id': 'continue', 'label': 'Continuer'}]},
                {'id': 'v36_parley_scene', 'title': 'Trêve',
                 'speaker': 'Jeanne', 'text': 'Parlons.',
                 'choices': [{'id': 'continue', 'label': 'Continuer'}]},
                {'id': 'v36_final', 'title': 'Après la décision',
                 'speaker': 'Jeanne', 'text': 'Avançons.',
                 'choices': [{'id': 'continue', 'label': 'Continuer'}]},
                {'id': 'v36_orphan', 'title': 'Scène isolée',
                 'speaker': '', 'text': 'Isolée.',
                 'choices': [{'id': 'continue', 'label': 'Continuer'}]},
            ],
            'entry_scenes': {}, 'after_mission': {},
            'during_tactical_event': {
                'garden/v36_origin': 'v36_dialogue',
            },
        }
        self.data = raw
        self.project = GameProject.from_dict(project_raw, content)

    def link(self, source_kind, source_id, target_kind, target_id, *,
             choice_id='', event_join='all', data=None, project=None,
             mission_id='garden'):
        return connect_visual_branch(
            data if data is not None else self.data,
            project if project is not None else self.project,
            mission_id, source_kind=source_kind, source_id=source_id,
            target_kind=target_kind, target_id=target_id,
            choice_id=choice_id, event_join=event_join)

    def trigger(self, data, eid):
        return next(e for m in data['missions'] if m['id'] == 'garden'
                    for e in m['triggers'] if e['id'] == eid)

    def build(self):
        data, project = self.link(
            'scene', 'v36_dialogue', 'event', 'v36_assault',
            choice_id='assault')
        data, project = self.link(
            'scene', 'v36_dialogue', 'event', 'v36_parley',
            choice_id='parley', data=data, project=project)
        for eid in ('v36_assault', 'v36_parley'):
            data, project = self.link(
                'event', 'v36_origin', 'event', eid,
                data=data, project=project)
            data, project = self.link(
                'event', eid, 'event', 'v36_join',
                event_join='any', data=data, project=project)
        for choice, sid in (
                ('assault', 'v36_assault_scene'),
                ('parley', 'v36_parley_scene')):
            data, project = self.link(
                'scene', 'v36_dialogue', 'scene', sid,
                choice_id=choice, data=data, project=project)
        data, project = self.link(
            'event', 'v36_join', 'scene', 'v36_final',
            data=data, project=project)
        return data, project

    def test_all_four_typed_links_preserve_canonical_data_and_history(self):
        original = deepcopy(self.data), deepcopy(self.project.to_dict())
        history = StudioHistory(self.data, self.project)
        data, project = self.build()
        self.assertEqual(self.trigger(data, 'v36_assault')['after_choice'],
                         {'scene': 'v36_dialogue', 'choice': 'assault'})
        self.assertEqual(self.trigger(data, 'v36_parley')['after'],
                         ['v36_origin'])
        self.assertEqual(self.trigger(data, 'v36_join')['after_any'],
                         ['v36_assault', 'v36_parley'])
        self.assertEqual(
            project.story['during_tactical_event']['garden/v36_join'],
            'v36_final')
        self.assertEqual(
            next(s for s in project.story['scenes']
                 if s['id'] == 'v36_dialogue')['choices'][0]['next_scene'],
            'v36_assault_scene')
        self.assertEqual((self.data, self.project.to_dict()), original)
        self.assertTrue(history.record(data, project))
        self.assertEqual((self.data, self.project.to_dict()), original)
        rollback_data, rollback_project = history.undo()
        self.assertEqual((rollback_data, rollback_project.to_dict()), original)
        replay_data, replay_project = history.redo()
        self.assertEqual((replay_data, replay_project.to_dict()),
                         (data, project.to_dict()))
        self.assertFalse(history.record(data, project))

    def test_real_player_has_exclusive_paths_and_replay(self):
        data, project = self.build()
        rules = authored_rules_for_document(data)
        content = Content.from_dict(data, rules=rules)
        for chosen, selected, denied in (
                ('assault', 'v36_assault', 'v36_parley'),
                ('parley', 'v36_parley', 'v36_assault')):
            with self.subTest(chosen=chosen):
                session = GameSession.new(content, project, 'main', rules=rules)
                session.start_mission('garden')
                self.assertEqual(session.tactical_story_pending,
                                 'v36_dialogue')
                self.assertNotIn('v36_join', session.active_battle.fired)
                session.choose_tactical_story_option(chosen)
                self.assertIn(selected, session.active_battle.fired)
                self.assertNotIn(denied, session.active_battle.fired)
                self.assertIn('v36_join', session.active_battle.fired)
                self.assertEqual(session.tactical_story_pending,
                                 'v36_' + chosen + '_scene')
                session.choose_tactical_story_option('continue')
                self.assertEqual(session.tactical_story_pending, 'v36_final')
                recorded = session.recording()
                restored = GameSession.from_recording(
                    recorded, content, project, rules=rules)
                self.assertEqual(restored.recording(), recorded)

    def test_invalid_links_fail_without_any_mutation(self):
        original = deepcopy(self.data), deepcopy(self.project.to_dict())
        specs = [
            ('scene', 'v36_dialogue', 'scene', 'v36_dialogue', 'assault', 'all'),
            ('scene', 'v36_dialogue', 'scene', 'missing', 'assault', 'all'),
            ('scene', 'v36_orphan', 'event', 'v36_assault', 'continue', 'all'),
            ('scene', 'v36_dialogue', 'event', 'no_event', 'assault', 'all'),
            ('scene', 'v36_dialogue', 'event', 'v36_assault', 'no_choice', 'all'),
            ('event', 'missing', 'event', 'v36_assault', '', 'all'),
            ('event', 'v36_origin', 'event', 'v36_origin', '', 'all'),
        ]
        for a, b, c, d, choice, join in specs:
            with self.subTest(a=a, b=b, c=c, d=d):
                with self.assertRaises(RuleError):
                    self.link(a, b, c, d, choice_id=choice, event_join=join)
                self.assertEqual((self.data, self.project.to_dict()), original)
        with self.assertRaises(RuleError):
            self.link('event', 'v36_origin', 'event', 'v36_assault',
                      event_join='xor')
        with self.assertRaises(RuleError):
            self.link('scene', 'v36_dialogue', 'scene', 'v36_assault_scene',
                      choice_id='assault', mission_id='bad_mission')

    def test_event_and_narrative_cycles_rejected(self):
        data, project = self.link(
            'event', 'v36_assault', 'event', 'v36_parley')
        with self.assertRaises(RuleError):
            self.link('event', 'v36_parley', 'event', 'v36_assault',
                      data=data, project=project)
        data, project = self.link(
            'scene', 'v36_dialogue', 'scene', 'v36_assault_scene',
            choice_id='assault')
        with self.assertRaises(RuleError):
            self.link('scene', 'v36_assault_scene', 'scene', 'v36_dialogue',
                      choice_id='continue', data=data, project=project)

    def test_projection_shows_detached_scenes_and_only_mission_events(self):
        palette = visual_target_palette(
            self.data, self.project, 'garden', {'v36_dialogue'},
            max_scenes=2, max_events=2)
        self.assertEqual(len(palette['scenes']), 2)
        self.assertEqual(len(palette['events']), 2)
        self.assertTrue(palette['scenes_truncated'])
        self.assertTrue(palette['events_truncated'])
        self.assertNotIn('v36_dialogue',
                         [s['id'] for s in palette['scenes']])
        self.assertTrue(all(s['kind'] == 'event'
                            for s in palette['events']))
        with self.assertRaises(RuleError):
            visual_target_palette(self.data, self.project, 'missing')


if __name__ == '__main__':
    unittest.main()
