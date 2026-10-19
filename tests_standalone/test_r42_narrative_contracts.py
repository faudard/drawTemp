"""R42.A headless contracts: explicit migration, reuse, IDs and legacy safety."""
from copy import deepcopy
import unittest

from drawtemp.sdk.reference import reference_project
from sporebound.game_project import GameProject
from sporebound.model import RuleError
from sporebound.narrative import StoryBook
from sporebound.narrative_r42 import (
    declare_subgraph, line_references, migrate_story_v1, set_dialogue_lines,
)


class NarrativeContractsR42Tests(unittest.TestCase):
    def setUp(self):
        self.content, self.legacy = reference_project()

    def test_v1_roundtrip_digest_and_first_choice_unchanged(self):
        before = deepcopy(self.legacy.to_dict())
        first = StoryBook(self.legacy.story, self.content,
                          self.legacy.campaigns)
        copy = GameProject.from_dict(before, self.content)
        second = StoryBook(copy.story, self.content, copy.campaigns)
        self.assertEqual(before, copy.to_dict())
        self.assertEqual(first.digest, second.digest)
        progress = copy.new_game('main', self.content)
        progress = second.choose(progress, 'enter')
        self.assertEqual(progress.story_pending, '')
        self.assertEqual(progress.story_history[-1],
                         {'scene': 'arrival', 'choice': 'enter'})

    def test_explicit_migration_keeps_legacy_untouched_and_new_save_required(self):
        original = deepcopy(self.legacy.to_dict())
        new = migrate_story_v1(self.legacy, self.content)
        self.assertEqual(self.legacy.to_dict(), original)
        self.assertNotIn('schema_version', original['story'])
        self.assertEqual(new.story['schema_version'], 2)
        self.assertEqual(line_references(new.story), ('arrival/line_001',))
        self.assertEqual(new.story['scenes'][0]['lines'][0]['speaker'], 'Jeanne')
        self.assertNotEqual(
            StoryBook(self.legacy.story, self.content, self.legacy.campaigns).digest,
            StoryBook(new.story, self.content, new.campaigns).digest)
        self.assertEqual(GameProject.from_dict(
            new.to_dict(), self.content).to_dict(), new.to_dict())
        with self.assertRaises(RuleError):
            migrate_story_v1(new, self.content)

    def test_authoring_multispeaker_line_identifiers_atomic_and_playable(self):
        migrated = migrate_story_v1(self.legacy, self.content)
        old = deepcopy(migrated.to_dict())
        new = set_dialogue_lines(migrated, self.content, 'arrival', [
            {'id': 'line_001', 'speaker': 'Jeanne', 'text': 'Nous partons.'},
            {'id': 'line_002', 'speaker': 'Capitaine', 'text': 'En avant !'},
        ])
        self.assertEqual(migrated.to_dict(), old)
        self.assertEqual(line_references(new.story),
                         ('arrival/line_001', 'arrival/line_002'))
        self.assertEqual(new.story['scenes'][0]['text'], 'Nous partons.')
        book = StoryBook(new.story, self.content, new.campaigns)
        progress = new.new_game('main', self.content)
        self.assertEqual(book.active_scene(progress)['lines'][1]['speaker'],
                         'Capitaine')
        self.assertEqual(book.choose(progress, 'enter').story_pending, '')
        with self.assertRaises(RuleError):
            set_dialogue_lines(new, self.content, 'arrival', [
                {'id': 'dup', 'speaker': 'A', 'text': 'Bonjour'},
                {'id': 'dup', 'speaker': 'B', 'text': 'Salut'},
            ])
        self.assertEqual(migrated.to_dict(), old)

    def test_named_shared_subgraph_uses_same_canonical_scene(self):
        upgraded = migrate_story_v1(self.legacy, self.content)
        data = upgraded.to_dict()
        data['story']['scenes'][0]['choices'] = [
            {'id': 'left', 'label': 'Gauche', 'next_scene': 'shared'},
            {'id': 'right', 'label': 'Droite', 'next_scene': 'shared',
             'effects': [{'kind': 'set_flag', 'flag': 'loyalty', 'value': 1}]},
        ]
        scene = {
            'id': 'shared', 'title': 'Retrouvailles', 'speaker': 'Capitaine',
            'text': 'Bienvenue.', 'lines': [
                {'id': 'line_001', 'speaker': 'Capitaine', 'text': 'Bienvenue.'}],
            'choices': [{'id': 'done', 'label': 'Continuer'}],
        }
        data['story']['scenes'].append(scene)
        project = GameProject.from_dict(data, self.content)
        declared = declare_subgraph(project, self.content, 'meeting', 'shared')
        self.assertEqual(declared.story['subgraphs'],
                         [{'id': 'meeting', 'entry_scene': 'shared'}])
        self.assertEqual(len(declared.story['scenes']), 2)
        self.assertEqual(project.story['subgraphs'], [])
        book = StoryBook(declared.story, self.content, declared.campaigns)
        progress = declared.new_game('main', self.content)
        progress = book.choose(progress, 'right')
        self.assertEqual(progress.story_flags['loyalty'], 1)
        self.assertEqual(book.active_scene(progress)['id'], 'shared')
        self.assertEqual(book.choose(progress, 'done').story_pending, '')
        with self.assertRaises(RuleError):
            declare_subgraph(declared, self.content, 'meeting', 'shared')

    def test_unknown_reference_cycle_schema_and_line_drift_fail_closed(self):
        source = migrate_story_v1(self.legacy, self.content).to_dict()
        variations = []
        missing = deepcopy(source)
        missing['story']['subgraphs'] = [
            {'id': 'lost', 'entry_scene': 'does_not_exist'}]
        variations.append(missing)
        drift = deepcopy(source)
        drift['story']['scenes'][0]['lines'][0]['text'] = 'Other truth'
        variations.append(drift)
        unknown = deepcopy(source)
        unknown['story']['schema_version'] = 99
        variations.append(unknown)
        effect = deepcopy(source)
        effect['story']['scenes'][0]['choices'][0]['effects'] = [
            {'kind': 'python', 'code': 'print(1)'}]
        variations.append(effect)
        cycle = deepcopy(source)
        cycle['story']['scenes'][0]['choices'][0]['next_scene'] = 'arrival'
        variations.append(cycle)
        for invalid in variations:
            with self.subTest(case=variations.index(invalid)):
                with self.assertRaises(RuleError):
                    GameProject.from_dict(invalid, self.content)

    def test_v2_longest_path_is_bounded(self):
        project = migrate_story_v1(self.legacy, self.content)
        data = project.to_dict()
        scenes = []
        for i in range(34):
            sid = 'node_' + str(i)
            text = 'Node ' + str(i)
            choice = {'id': 'continue', 'label': 'Continuer'}
            if i < 33:
                choice['next_scene'] = 'node_' + str(i + 1)
            scenes.append({
                'id': sid, 'title': text, 'speaker': '', 'text': text,
                'lines': [{'id': 'line_001', 'speaker': '', 'text': text}],
                'choices': [choice],
            })
        data['story']['scenes'] = scenes
        data['story']['entry_scenes'] = {'main': 'node_0'}
        with self.assertRaises(RuleError):
            GameProject.from_dict(data, self.content)
        scenes.pop()
        scenes[-1]['choices'][0].pop('next_scene')
        GameProject.from_dict(data, self.content)


if __name__ == '__main__':
    unittest.main()
