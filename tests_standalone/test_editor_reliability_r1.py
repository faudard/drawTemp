"""R1.5/R1.6 regression gates: incremental reports, crash drafts, four-edit round trip."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_object
from sporebound.editor import Document
from sporebound.editor_architecture import (
    EditingContext, StructureCommand, EntityCommand, TacticalEventCommand)
from sporebound.editor_reliability import (
    EditRecoveryJournal, IncrementalValidator, ObsoleteCalculation)
from sporebound.event_composer import action, condition, save_event
from sporebound.game_project import GameProject
from sporebound.iso_structures import place_structure
from sporebound.model import Content, RuleError
from sporebound.studio_transaction import StudioHistory, StudioTransactionStore
from sporebound.tactical_rpg3 import authored_rules_for_document


class ReliabilityR1Tests(unittest.TestCase):
    MID = 'reliability_r1'

    @classmethod
    def setUpClass(cls):
        raw = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                cls.MID, 'R1 gate', 20, 20)
        raw = place_structure(raw, cls.MID, 'Pont', (6, 6))
        raw = add_object(raw, cls.MID, 'door_a', 'door', [3, 3])
        raw = add_object(raw, cls.MID, 'door_b', 'door', [4, 3])
        raw = add_object(raw, cls.MID, 'switch_a', 'switch', [2, 3],
                         link='door_a')
        raw = save_event(raw, cls.MID, 'bridge_alarm',
                         condition('tick', tick=8),
                         [action('message', text='Alerte sur le pont')])
        cls.raw = raw
        cls.project = GameProject.default(Content.from_dict(raw)).to_dict()

    def setUp(self):
        self.doc = Document(Content.from_dict(self.raw))
        self.ctx = EditingContext(self.doc, lambda: self.MID)

    def mission(self):
        return next(m for m in self.doc.data['missions']
                    if m['id'] == self.MID)

    def test_r1_four_actions_undo_redo_in_order_player_compatible(self):
        initial = deepcopy(self.doc.data)
        history = StudioHistory(self.doc.data, self.project)
        actor_id = self.mission()['units'][0]['id']
        commands = [
            StructureCommand((6, 6), anchor=(9, 9)),
            EntityCommand('edit', 'actor', actor_id,
                          fields=(('name', 'R1 Jeanne'),)),
            EntityCommand('edit', 'object', 'switch_a',
                          fields=(('link', 'door_b'),)),
            TacticalEventCommand('bridge_alarm', condition('tick', tick=12)),
        ]
        notices = []
        for command in commands:
            preview = self.ctx.preview(command)
            self.assertEqual(len(self.doc.undo_stack), len(notices))
            notices.append(self.ctx.apply(preview))
            self.assertTrue(history.record(self.doc.data, self.project))
        final = deepcopy(self.doc.data)
        self.assertEqual(tuple(self.mission()['structures'][-1]['anchor']),
                         (9, 9))
        self.assertEqual(self.mission()['units'][0]['name'], 'R1 Jeanne')
        self.assertEqual(next(o['link'] for o in self.mission()['objects']
                              if o['id'] == 'switch_a'), 'door_b')
        self.assertEqual(next(e['value'] for e in self.mission()['triggers']
                              if e['id'] == 'bridge_alarm'), 12)
        self.assertEqual(len(self.doc.undo_stack), 4)
        self.assertEqual([n.revision for n in notices], [1, 2, 3, 4])

        for _ in range(4):
            restored, game = history.undo()
            self.doc.data = restored
            self.assertEqual(game.to_dict(), self.project)
        self.assertEqual(self.doc.data, initial)
        self.assertFalse(history.can_undo)
        for _ in range(4):
            restored, game = history.redo()
            self.doc.data = restored
            self.assertEqual(game.to_dict(), self.project)
        self.assertEqual(self.doc.data, final)
        self.assertFalse(history.can_redo)
        canonical = Content.from_dict(
            self.doc.data, rules=authored_rules_for_document(self.doc.data))
        self.assertEqual(GameProject.from_dict(self.project, canonical).to_dict(),
                         self.project)

    def test_superseded_preview_and_validation_never_publish(self):
        actor_id = self.mission()['units'][0]['id']
        preview = self.ctx.preview(EntityCommand(
            'edit', 'actor', actor_id, fields=(('name', 'Too old'),)))
        original = deepcopy(self.doc.data)
        validator = self.ctx.diagnostics
        before = validator.validate(self.doc.data)
        self.assertEqual(validator.validate(self.doc.data).rescanned_missions, ())
        events = []
        def supersede(mid):
            events.append(mid)
            if len(events) == 1:
                validator.cancel()
        with self.assertRaises(ObsoleteCalculation):
            validator.validate(self.doc.data, on_scan=supersede)
        self.assertFalse(validator.is_current(before, self.doc.data))
        self.assertEqual(original, self.doc.data)
        self.ctx.execute(StructureCommand((6, 6), anchor=(10, 10)))
        current = deepcopy(self.doc.data)
        with self.assertRaises(RuleError):
            self.ctx.apply(preview)
        self.assertEqual(self.doc.data, current)
        self.assertEqual(len(self.doc.undo_stack), 1)

    def test_incremental_only_rescans_modified_mission(self):
        validator = IncrementalValidator()
        first = validator.validate(self.raw, self.project)
        self.assertIn(self.MID, first.rescanned_missions)
        self.assertEqual(validator.validate(self.raw, self.project).rescanned_missions,
                         ())
        updated = deepcopy(self.raw)
        next(m for m in updated['missions'] if m['id'] == self.MID)['name'] += ' edited'
        third = validator.validate(updated, self.project)
        self.assertEqual(third.rescanned_missions, (self.MID,))
        self.assertTrue(validator.is_current(third, updated, self.project))

    def test_cross_references_have_navigable_errors(self):
        bad = deepcopy(self.raw)
        m = next(m for m in bad['missions'] if m['id'] == self.MID)
        next(o for o in m['objects'] if o['id'] == 'switch_a')['link'] = 'missing'
        m['triggers'][0]['after'] = ['missing_event']
        report = IncrementalValidator().validate(bad, self.project)
        self.assertIn(('object.link', f'map_object:{self.MID}/switch_a'),
                      {(e.code, e.resource) for e in report.errors})
        self.assertIn(('event.after', f'event:{self.MID}/bridge_alarm'),
                      {(e.code, e.resource) for e in report.errors})

    def test_work_journal_explicit_restore_never_overwrites_disk(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'mission.json'
            store = StudioTransactionStore(path)
            store.save(self.raw, self.project)
            disk_before = [p.read_bytes() for p in store.paths]
            self.ctx.execute(StructureCommand((6, 6), anchor=(9, 9)))
            draft = deepcopy(self.doc.data)
            journal = EditRecoveryJournal(path)
            self.assertTrue(journal.checkpoint(
                draft, self.project, expected_disk=store.revisions(),
                dirty=(True, False)))
            self.assertTrue(journal.pending)
            restored, game = EditRecoveryJournal(path).restore()
            self.assertEqual(restored, draft)
            self.assertEqual(game, self.project)
            self.assertEqual([p.read_bytes() for p in store.paths], disk_before)
            sidecar = json.loads(journal.path.read_text(encoding='utf-8'))
            self.assertEqual(sidecar['dirty'], [True, False])
            self.assertNotIn('undo_stack', str(sidecar))
            journal.discard()
            self.assertFalse(journal.pending)

    def test_external_disk_change_and_corrupt_journal_fail_closed(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'mission.json'
            store = StudioTransactionStore(path)
            store.save(self.raw, self.project)
            journal = EditRecoveryJournal(path)
            journal.checkpoint(self.raw, self.project,
                               expected_disk=store.revisions(),
                               dirty=(True, False))
            sidecar = json.loads(journal.path.read_text(encoding='utf-8'))
            sidecar['digest'] = '0' * 64
            journal.path.write_text(json.dumps(sidecar), encoding='utf-8')
            with self.assertRaisesRegex(RuleError, 'altéré'):
                journal.restore()
            journal.checkpoint(self.raw, self.project,
                               expected_disk=store.revisions(),
                               dirty=(True, False))
            store.content_path.write_bytes(store.content_path.read_bytes() + b' ')
            with self.assertRaisesRegex(RuleError, 'changé sur disque'):
                journal.restore()
            self.assertTrue(journal.pending)

    def test_history_change_callback_after_record_and_restore(self):
        history = StudioHistory(self.raw, self.project)
        calls = []
        history.on_change = lambda: calls.append('changed')
        updated = deepcopy(self.raw)
        next(m for m in updated['missions'] if m['id'] == self.MID)['name'] = 'R1+'
        self.assertTrue(history.record(updated, self.project))
        history.undo()
        history.redo()
        self.assertEqual(calls, ['changed'] * 3)


if __name__ == '__main__':
    unittest.main()
