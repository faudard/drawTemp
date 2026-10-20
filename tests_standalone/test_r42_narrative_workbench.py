"""R42.B1 Narrative Studio: canonical preview/apply/undo and source references."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.narrative_workbench_r42 import NarrativeWorkbench
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession


class NarrativeWorkbenchR42Tests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.content = content
        self.editor = AuthoringSession.new(content, project)
        self.studio = NarrativeWorkbench(self.editor)

    def test_explicit_migration_preview_apply_undo_redo(self):
        before = self.editor.snapshot().to_dict()
        plan = self.studio.preview_migrate()
        self.assertEqual(self.editor.snapshot().to_dict(), before)
        self.studio.apply(plan)
        self.assertEqual(self.studio.graph()['version'], 2)
        self.assertEqual(self.studio.inspect('arrival')['line_ids'],
                         ('arrival/line_001',))
        self.studio.undo()
        self.assertEqual(self.editor.snapshot().to_dict()['project'],
                         before['project'])
        self.studio.redo()
        self.assertEqual(self.studio.graph()['version'], 2)

    def test_multispeaker_lines_stable_and_player_can_load_project(self):
        self.studio.apply(self.studio.preview_migrate())
        new_lines = [
            {'id': 'welcome', 'speaker': 'Jeanne', 'text': 'Allons-y.'},
            {'id': 'reply', 'speaker': 'Capitaine', 'text': 'Je vous suis.'},
        ]
        plan = self.studio.preview_lines('arrival', new_lines)
        self.assertEqual(len(self.studio.inspect('arrival')['line_ids']), 1)
        revision = self.editor.revision
        self.studio.apply(plan)
        self.assertEqual(self.editor.revision, revision + 1)
        self.assertEqual(self.studio.inspect('arrival')['line_ids'],
                         ('arrival/welcome', 'arrival/reply'))
        project = GameProject.from_dict(
            self.editor.snapshot().to_dict()['project'], self.content)
        game = GameSession.new(self.content, project, 'main')
        self.assertEqual(game.active_scene()['lines'][1]['text'], 'Je vous suis.')
        self.studio.undo()
        self.assertEqual(self.studio.inspect('arrival')['line_ids'],
                         ('arrival/line_001',))

    def test_shared_links_source_usage_subgraphs_and_atomic_creation(self):
        self.studio.apply(self.studio.preview_migrate())
        self.studio.apply(self.studio.preview_create_scene(
            'captain', 'Rencontre', 'Capitaine', 'À vos ordres.'))
        self.studio.apply(self.studio.preview_link(
            'arrival', 'enter', 'captain'))
        self.studio.apply(self.studio.preview_subgraph('first_meeting', 'captain'))
        graph = self.studio.graph()
        self.assertEqual([e['to'] for e in graph['edges']], ['captain'])
        entry = self.studio.inspect('captain')
        self.assertTrue(any(x.get('scene') == 'arrival'
                            and x.get('choice') == 'enter'
                            for x in entry['incoming']))
        self.assertTrue(any(x.get('source') == 'subgraph' for x in entry['incoming']))
        self.assertEqual(len(graph['nodes']), 2)
        with self.assertRaises(AuthoringError):
            self.studio.preview_link('captain', 'continue', 'arrival')
        self.assertEqual(len(self.studio.graph()['edges']), 1)

    def test_typed_state_preview_validation_and_revision_staleness(self):
        self.studio.apply(self.studio.preview_migrate())
        before = deepcopy(self.studio.document())
        plan = self.studio.preview_state(
            identifier='captain', kind='relation',
            scope='campaign', owner='main', initial=5)
        self.assertEqual(self.studio.document(), before)
        self.studio.apply(plan)
        self.assertEqual(self.studio.document()['state'][0]['initial'], 5)
        stale = self.studio.preview_state(
            identifier='ally', kind='bool',
            scope='scene', owner='arrival', initial=True)
        self.studio.undo()
        with self.assertRaises(AuthoringError) as error:
            self.studio.apply(stale)
        self.assertEqual(error.exception.code, 'stale_revision')
        self.assertNotIn('state', self.studio.document())

    def test_vs42_template_preview_is_two_document_undoable_transaction(self):
        before = self.editor.snapshot().to_dict()
        preview = self.studio.preview_captain_slice()
        self.assertEqual(self.editor.snapshot().to_dict(), before)
        self.studio.apply(preview)
        now = self.editor.snapshot().to_dict()
        self.assertEqual(now['project']['title'], 'La loyauté du capitaine')
        self.assertEqual(now['project']['story']['schema_version'], 2)
        self.assertGreater(len(now['content']['missions']),
                           len(before['content']['missions']))
        self.assertEqual(len(now['project']['campaign_flow']['endings']), 3)
        self.studio.undo()
        restored = self.editor.snapshot().to_dict()
        self.assertEqual(restored['content'], before['content'])
        self.assertEqual(restored['project'], before['project'])
        self.studio.redo()
        self.assertEqual(self.editor.snapshot().to_dict()['project'],
                         now['project'])

    def test_invalid_lines_do_not_mutate_documents(self):
        self.studio.apply(self.studio.preview_migrate())
        original = self.editor.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            self.studio.preview_lines('arrival', [
                {'id': 'twice', 'speaker': 'A', 'text': 'A'},
                {'id': 'twice', 'speaker': 'B', 'text': 'B'},
            ])
        with self.assertRaises(AuthoringError):
            self.studio.preview_state(
                identifier='wrong', kind='relation',
                scope='campaign', owner='main', initial=999)
        self.assertEqual(self.editor.snapshot().to_dict(), original)


if __name__ == '__main__':
    unittest.main()
