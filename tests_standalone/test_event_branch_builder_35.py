"""3.5 cross-resource map-to-choice authoring, previews and real replay."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.event_branch_builder import author_choice_fork, branch_recipe
from sporebound.event_branches import preview_choice_routes
from sporebound.event_composer import save_event, condition, action
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.tactical_rpg3 import authored_rules_for_document


class VisualChoiceBuilderTests(unittest.TestCase):
    def setUp(self):
        self.data = Content.load(DEFAULT_CONTENT).to_dict()
        self.project = GameProject.default(Content.from_dict(self.data))
        self.mid = 'garden'
        self.branches = branch_recipe(
            first_id='assault', first_label='Assaillir',
            first_event='fork_assault', first_action='hazard',
            first_text='L’assaut est lancé', first_amount=9,
            second_id='parley', second_label='Négocier',
            second_event='fork_parley', second_action='message',
            second_text='La garnison accepte de discuter',
            second_amount=0)

    def build(self, *, source='fork_source', reunion='fork_reunion',
              src_data=None, src_project=None, **kwargs):
        options = dict(
            origin_event_id=source, origin_cell=[6, 6],
            scene_id='fork_dialogue', title='Quel chemin ?',
            text='Jeanne demande de choisir la voie.',
            branches=deepcopy(self.branches),
            reunion_event_id=reunion,
            reunion_message='Les alliés se réunissent',
            speaker='Jeanne')
        options.update(kwargs)
        return author_choice_fork(
            src_data if src_data is not None else self.data,
            src_project if src_project is not None else self.project,
            self.mid, **options)

    def event(self, data, event_id):
        return next(row for mission in data['missions'] if mission['id'] == self.mid
                    for row in mission['triggers'] if row['id'] == event_id)

    def test_map_creation_links_scene_fork_events_and_reunion(self):
        original = deepcopy(self.data), deepcopy(self.project.to_dict())
        data, project = self.build()
        self.assertEqual(self.event(data, 'fork_source'),
                         {'id': 'fork_source', 'condition': 'enter',
                          'pos': [6, 6],
                          'actions': [{'kind': 'message',
                                      'text': 'Quel chemin ?'}]})
        self.assertEqual(
            self.event(data, 'fork_assault')['after_choice'],
            {'scene': 'fork_dialogue', 'choice': 'assault'})
        self.assertEqual(self.event(data, 'fork_parley')['after'],
                         ['fork_source'])
        self.assertEqual(self.event(data, 'fork_reunion')['after_any'],
                         ['fork_assault', 'fork_parley'])
        self.assertEqual(
            project.story['during_tactical_event']['garden/fork_source'],
            'fork_dialogue')
        scenes = {row['id']: row for row in project.story['scenes']}
        self.assertEqual(len(scenes), 4)
        self.assertEqual([x['next_scene'] for x in
                          scenes['fork_dialogue']['choices']],
                         ['fork_dialogue_assault', 'fork_dialogue_parley'])
        self.assertEqual(scenes['fork_dialogue_assault']['choices'][0]['next_scene'],
                         'fork_dialogue_reunion')
        self.assertEqual(original, (self.data, self.project.to_dict()))
        self.assertEqual(Content.from_dict(data).to_dict(), data)
        self.assertEqual(GameProject.from_dict(project.to_dict(),
                                               Content.from_dict(data)).to_dict(),
                         project.to_dict())

    def test_preview_uses_real_battle_and_does_not_mutate_authored_files(self):
        data, project = self.build()
        untouched = deepcopy(data), deepcopy(project.to_dict())
        report = preview_choice_routes(data, project, self.mid, 'fork_source',
                                       scenario='satisfied')
        self.assertTrue(report['source_fired'])
        self.assertEqual(report['replay_verified'], None)
        paths = {row['choice_id']: row for row in report['routes']}
        self.assertEqual(paths['assault']['fired_ids'],
                         ['fork_assault', 'fork_reunion'])
        self.assertEqual(paths['parley']['fired_ids'],
                         ['fork_parley', 'fork_reunion'])
        self.assertEqual(paths['assault']['next_scene'],
                         'fork_dialogue_assault')
        self.assertEqual(paths['parley']['next_scene'],
                         'fork_dialogue_parley')
        self.assertTrue(any('danger' in text.lower()
                            for text in paths['assault']['changes']))
        self.assertTrue(any(x['event_id'] == 'fork_parley'
                            for x in paths['assault']['excluded']))
        self.assertEqual(untouched, (data, project.to_dict()))

    def test_true_player_choice_and_game_session_save_replay(self):
        # Reuse an existing tick-zero trigger as an entry: the wizard supports
        # either an existing source or a new map-cell entry event.
        raw = save_event(
            self.data, self.mid, 'existing_origin',
            condition('tick', tick=0),
            [action('message', text='Décision')])
        data, project = self.build(source='existing_origin',
                                   src_data=raw)
        rules = authored_rules_for_document(data)
        content = Content.from_dict(data, rules=rules)
        for cid, expected, excluded in (
                ('assault', 'fork_assault', 'fork_parley'),
                ('parley', 'fork_parley', 'fork_assault')):
            with self.subTest(cid=cid):
                session = GameSession.new(content, project, 'main', rules=rules)
                session.start_mission(self.mid)
                self.assertEqual(session.tactical_story_pending,
                                 'fork_dialogue')
                session.choose_tactical_story_option(cid)
                self.assertIn(expected, session.active_battle.fired)
                self.assertNotIn(excluded, session.active_battle.fired)
                self.assertIn('fork_reunion', session.active_battle.fired)
                self.assertEqual(session.tactical_story_pending,
                                 'fork_dialogue_' + cid)
                session.choose_tactical_story_option('continue')
                self.assertEqual(session.tactical_story_pending,
                                 'fork_dialogue_reunion')
                recorded = session.recording()
                restored = GameSession.from_recording(
                    recorded, content, project, rules=rules)
                self.assertEqual(restored.recording(), recorded)
                self.assertEqual(restored.active_battle.fired,
                                 session.active_battle.fired)

    def test_no_reunion_and_existing_scene_collection_is_preserved(self):
        source, project = self.build(reunion='')
        next_data, next_project = author_choice_fork(
            source, project, self.mid, origin_event_id='second_origin',
            origin_cell=[5, 6], scene_id='second_choice',
            title='Seconde décision', text='Que faire ?',
            branches=[
                {**self.branches[0], 'event_id': 'second_assault'},
                {**self.branches[1], 'event_id': 'second_parley'},
            ])
        self.assertEqual(len(project.story['scenes']), 3)
        self.assertEqual(len(next_project.story['scenes']), 6)
        self.assertEqual(len(next_project.story['during_tactical_event']), 2)
        self.assertEqual(source, source)  # mutation only through returned copies
        self.assertIn('second_origin', [e['id'] for m in next_data['missions']
                                       for e in m['triggers']])

    def test_failed_authoring_changes_neither_content_nor_project(self):
        before = deepcopy(self.data), deepcopy(self.project.to_dict())
        cases = [
            {'branches': [self.branches[0], self.branches[0]]},
            {'branches': [{**self.branches[0], 'amount': 99999},
                          self.branches[1]]},
            {'scene_id': 'x' * 65},
            {'branches': [{**self.branches[0], 'event_id': 'spore_pulse'},
                          self.branches[1]]},
            {'origin_cell': [-1, 99]},
            {'reunion_event_id': 'fork_assault'},
        ]
        for options in cases:
            with self.subTest(options=options):
                with self.assertRaises((RuleError, ValueError)):
                    self.build(**options)
                self.assertEqual(before, (self.data, self.project.to_dict()))


if __name__ == '__main__':
    unittest.main()
