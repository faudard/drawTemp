"""R1.7 — revision leases and the real Studio-to-Player acceptance gate.

No Tk dependency: use Document, EditingContext, StudioHistory and GameSession.
"""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_object
from sporebound.editor import Document
from sporebound.editor_architecture import (
    EditingContext, EntityCommand, StructureCommand, TacticalEventCommand)
from sporebound.event_composer import action, condition, save_event
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.iso_structures import place_structure
from sporebound.model import Content, RuleError
from sporebound.studio_transaction import StudioHistory
from sporebound.tactical_rpg3 import authored_rules_for_document


class RevisionLeaseTests(unittest.TestCase):
    MID = 'r1_gate'

    @classmethod
    def setUpClass(cls):
        raw = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                cls.MID, 'R1 acceptance', 20, 20)
        raw = place_structure(raw, cls.MID, 'Pont', (6, 6))
        raw = add_object(raw, cls.MID, 'door_old', 'door', [3, 3])
        raw = add_object(raw, cls.MID, 'door_new', 'door', [4, 3])
        raw = add_object(raw, cls.MID, 'switch_a', 'switch', [2, 3],
                         link='door_old')
        raw = save_event(raw, cls.MID, 'alarm',
                         condition('tick', tick=8),
                         [action('message', text='Pont menacé')])
        cls.raw = raw
        content = Content.from_dict(raw, rules=authored_rules_for_document(raw))
        cls.original_project = GameProject.default(content).to_dict()
        cls.original_project['campaigns'][0]['start_mission'] = cls.MID
        GameProject.from_dict(cls.original_project, content)

    def setUp(self):
        self.doc = Document(Content.from_dict(self.raw))
        self.context = EditingContext(self.doc, lambda: self.MID)
        self.actor_id = next(m for m in self.doc.data['missions']
                             if m['id'] == self.MID)['units'][0]['id']

    def _player(self, data, project):
        """Boot exactly the canonical mission via the normal GameSession path."""
        content = Content.from_dict(data,
                                    rules=authored_rules_for_document(data))
        manifest = GameProject.from_dict(project, content)
        session = GameSession.new(content, manifest, 'main', seed=42)
        battle = session.start_mission(self.MID)
        self.assertEqual(battle.mission.id, self.MID)
        return battle

    def _observed(self, battle):
        mission = battle.mission
        return {
            'anchor': tuple(next(row['anchor'] for row in mission.structures
                                 if row['name'] == 'Pont')),
            'actor': next(unit.name for unit in battle.units
                          if unit.id == self.actor_id),
            'link': next(obj['link'] for obj in mission.objects
                         if obj['id'] == 'switch_a'),
            'tick': next(event['value'] for event in mission.triggers
                         if event['id'] == 'alarm'),
        }

    def test_four_operations_and_global_undo_redo_match_player(self):
        baseline = deepcopy(self.doc.data)
        project = deepcopy(self.original_project)
        history = StudioHistory(baseline, project)
        base_snapshot = self._observed(self._player(baseline, project))
        actions = [
            StructureCommand((6, 6), anchor=(9, 9)),
            EntityCommand('edit', 'actor', self.actor_id,
                          fields=(('name', 'Edited R1'),)),
            EntityCommand('edit', 'object', 'switch_a',
                          fields=(('link', 'door_new'),)),
            TacticalEventCommand('alarm', condition('tick', tick=12)),
        ]
        for index, action in enumerate(actions, 1):
            preview = self.context.preview(action)
            self.context.apply(preview)
            self.assertEqual(len(self.doc.undo_stack), index)
            self.assertTrue(history.record(self.doc.data, project))
        edited = deepcopy(self.doc.data)
        expected = {'anchor': (9, 9), 'actor': 'Edited R1',
                    'link': 'door_new', 'tick': 12}
        self.assertEqual(self._observed(self._player(edited, project)), expected)

        for _ in range(4):
            restored, manifest = history.undo()
            self.doc.restore_snapshot(restored)
            project = manifest.to_dict()
            self._player(self.doc.data, project)
        self.assertEqual(self.doc.data, baseline)
        self.assertEqual(self._observed(self._player(self.doc.data, project)),
                         base_snapshot)
        self.assertFalse(history.can_undo)
        for _ in range(4):
            restored, manifest = history.redo()
            self.doc.restore_snapshot(restored)
            project = manifest.to_dict()
            self._player(self.doc.data, project)
        self.assertEqual(self.doc.data, edited)
        self.assertEqual(self._observed(self._player(self.doc.data, project)),
                         expected)
        self.assertFalse(history.can_redo)
        self.assertFalse(self.doc.undo_stack)
        self.assertFalse(self.doc.redo_stack)

    def test_aba_undo_must_reject_preview_even_if_bytes_match(self):
        pending = self.context.preview(EntityCommand(
            'edit', 'actor', self.actor_id, fields=(('name', 'obsolete'),)))
        initial = deepcopy(self.doc.data)
        first_revision = self.doc.mutation_revision
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         'Tour', (11, 11)))
        self.doc.undo()
        self.assertEqual(self.doc.data, initial)
        self.assertGreater(self.doc.mutation_revision, first_revision)
        with self.assertRaisesRegex(RuleError, 'revision'):
            self.context.apply(pending)
        self.assertEqual(self.doc.data, initial)
        self.assertEqual(len(self.doc.undo_stack), 0)
        self.assertEqual(len(self.doc.redo_stack), 1)

    def test_same_bytes_after_studio_restore_must_reject_preview(self):
        project = deepcopy(self.original_project)
        history = StudioHistory(self.doc.data, project)
        pending = self.context.preview(EntityCommand(
            'edit', 'actor', self.actor_id, fields=(('name', 'obsolete'),)))
        baseline = deepcopy(self.doc.data)
        self.context.execute(EntityCommand(
            'edit', 'actor', self.actor_id, fields=(('name', 'intermediate'),)))
        history.record(self.doc.data, project)
        restored, _ = history.undo()
        self.doc.restore_snapshot(restored)
        self.assertEqual(self.doc.data, baseline)
        with self.assertRaisesRegex(RuleError, 'revision'):
            self.context.apply(pending)

    def test_project_only_history_revokes_content_preview(self):
        pending = self.context.preview(EntityCommand(
            'edit', 'actor', self.actor_id, fields=(('name', 'obsolete'),)))
        changed_project = deepcopy(self.original_project)
        changed_project['title'] = 'Modified in Story Studio'
        history = StudioHistory(self.doc.data, self.original_project)
        # This is the same callback installed by the editor for any history
        # mutation, including changes that touch GameProject only.
        history.on_change = self.context.invalidate
        history.record(self.doc.data, changed_project)
        self.assertEqual(self.doc.data, self.raw)
        with self.assertRaisesRegex(RuleError, 'context changed'):
            self.context.apply(pending)

    def test_reload_same_document_content_cannot_reuse_preview(self):
        pending = self.context.preview(EntityCommand(
            'edit', 'actor', self.actor_id, fields=(('name', 'obsolete'),)))
        self.context.document = Document(Content.from_dict(self.doc.data))
        with self.assertRaisesRegex(RuleError, 'revision'):
            self.context.apply(pending)

    def test_rejected_preview_keeps_published_history_and_player_unchanged(self):
        pending = self.context.preview(EntityCommand(
            'edit', 'actor', self.actor_id, fields=(('name', 'obsolete'),)))
        initial = deepcopy(self.doc.data)
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         'Tour', (11, 11)))
        self.doc.undo()
        self.assertEqual(self.doc.data, initial)
        before = self._observed(self._player(self.doc.data, self.original_project))
        with self.assertRaises(RuleError):
            self.context.apply(pending)
        self.assertEqual(
            self._observed(self._player(self.doc.data, self.original_project)),
            before)


if __name__ == '__main__':
    unittest.main()
