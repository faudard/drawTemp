"""R42.A2: typed narrative state, canonical effects, save/replay integrity."""
from copy import deepcopy
import unittest

from drawtemp.sdk.reference import reference_project
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from sporebound.narrative_r42 import migrate_story_v1
from sporebound.narrative_state_r42 import (
    declare_state, state_key, state_condition, state_effect, state_snapshot,
)


class NarrativeStateR42Tests(unittest.TestCase):
    def setUp(self):
        self.content, self.legacy = reference_project()
        self.v2 = migrate_story_v1(self.legacy, self.content)

    def project_with_relation(self, value=0):
        return declare_state(self.v2, self.content,
                             identifier='captain', kind='relation',
                             scope='campaign', owner='main', initial=value)

    def test_declaration_is_copy_on_write_and_campaign_is_authority(self):
        before = deepcopy(self.v2.to_dict())
        project = self.project_with_relation(20)
        self.assertEqual(before, self.v2.to_dict())
        spec = project.story['state'][0]
        key = state_key(spec)
        self.assertEqual(key, 'r42_c_main_captain')
        session = GameSession.new(self.content, project, 'main')
        self.assertEqual(session.progress.story_flags[key], 20)
        self.assertEqual(session.narrative_state(),
                         ({'id': 'captain', 'kind': 'relation',
                           'scope': 'campaign', 'owner': 'main',
                           'flag': key, 'value': 20},))
        self.assertEqual(project.to_dict(),
                         GameProject.from_dict(project.to_dict(), self.content).to_dict())

    def test_native_r9_conditions_effects_and_session_restore(self):
        project = self.project_with_relation(5)
        spec = project.story['state'][0]
        condition = state_condition(project.story, identifier='captain',
                                    scope='campaign', owner='main',
                                    operator='gte', value=5)
        effect = state_effect(project.story, identifier='captain',
                              scope='campaign', owner='main',
                              action='add', value=7)
        data = project.to_dict()
        scene = data['story']['scenes'][0]
        scene['choices'][0]['when'] = condition
        scene['choices'][0]['effects'] = [effect, {'kind': 'gold', 'amount': 9}]
        scene['choices'].append({'id': 'fallback', 'label': 'Partir'})
        project = GameProject.from_dict(data, self.content)
        session = GameSession.new(self.content, project, 'main', seed=3)
        self.assertEqual([c['id'] for c in session.available_choices()],
                         ['enter', 'fallback'])
        baseline = session.recording()
        same = GameSession.from_recording(baseline, self.content, project)
        self.assertEqual(same.narrative_state(), session.narrative_state())
        session.choose_story_option('enter')
        key = state_key(spec)
        self.assertEqual(session.progress.story_flags[key], 12)
        self.assertEqual(session.progress.gold, 9)
        self.assertEqual(session.progress.story_history,
                         [{'scene': 'arrival', 'choice': 'enter'}])
        with self.assertRaises(RuleError):
            session.choose_story_option('enter')
        self.assertEqual(session.progress.gold, 9)
        record = session.recording()
        restored = GameSession.from_recording(record, self.content, project)
        self.assertEqual(restored.recording(), record)
        self.assertEqual(restored.narrative_state(), session.narrative_state())

    def test_overflow_and_bad_effect_are_atomic(self):
        project = self.project_with_relation(95)
        effect = state_effect(project.story, identifier='captain',
                              scope='campaign', owner='main',
                              action='add', value=10)
        raw = project.to_dict()
        raw['story']['scenes'][0]['choices'][0]['effects'] = [
            {'kind': 'gold', 'amount': 9}, effect]
        project = GameProject.from_dict(raw, self.content)
        session = GameSession.new(self.content, project, 'main')
        before = session.recording()
        with self.assertRaises(RuleError):
            session.choose_story_option('enter')
        self.assertEqual(session.recording(), before)
        self.assertEqual(session.progress.story_history, [])

    def test_missing_or_wrong_type_saved_flag_fails_even_with_recomputed_checksum(self):
        project = self.project_with_relation(0)
        session = GameSession.new(self.content, project, 'main')
        flag = state_key(project.story['state'][0])
        original = session.recording()
        for corrupted in (None, True, 101, -101, '5'):
            rec = deepcopy(original)
            if corrupted is None:
                del rec['progress']['story_flags'][flag]
            else:
                rec['progress']['story_flags'][flag] = corrupted
            rec['digest'] = digest({key: value for key, value in rec.items()
                                    if key != 'digest'})
            with self.subTest(corrupted=corrupted), self.assertRaises(RuleError):
                GameSession.from_recording(rec, self.content, project)
        self.assertEqual(session.recording(), original)

    def test_references_and_types_reject_ambiguous_authoring(self):
        project = self.project_with_relation()
        with self.assertRaises(RuleError):
            declare_state(project, self.content, identifier='captain',
                          kind='relation', scope='campaign', owner='main',
                          initial=0)
        with self.assertRaises(RuleError):
            declare_state(self.v2, self.content, identifier='lost',
                          kind='bool', scope='scene', owner='unknown',
                          initial=True)
        with self.assertRaises(RuleError):
            state_condition(project.story, identifier='captain',
                            scope='campaign', owner='main', operator='eq',
                            value=True)
        with self.assertRaises(RuleError):
            state_effect(project.story, identifier='captain',
                         scope='campaign', owner='main', action='set', value=101)
        with self.assertRaises(RuleError):
            state_effect(project.story, identifier='missing',
                         scope='campaign', owner='main', action='set', value=0)

        data = project.to_dict()
        data['story']['scenes'][0]['choices'][0]['when'] = {
            'flag': 'r42_c_main_missing', 'eq': 0}
        data['story']['scenes'][0]['choices'].append(
            {'id': 'fallback', 'label': 'Retour'})
        with self.assertRaises(RuleError):
            GameProject.from_dict(data, self.content)

    def test_boolean_and_mission_scopes_use_same_campaign_ledger(self):
        first = declare_state(self.v2, self.content, identifier='admitted',
                              kind='bool', scope='scene', owner='arrival',
                              initial=False)
        mission = next(iter(self.content.missions))
        second = declare_state(first, self.content, identifier='phase',
                               kind='int', scope='mission', owner=mission,
                               initial=3)
        self.assertEqual(len(second.story['state']), 2)
        prog = second.new_game('main', self.content)
        values = state_snapshot(second.story, prog)
        self.assertEqual([v['value'] for v in values], [False, 3])
        self.assertEqual(
            state_effect(second.story, identifier='admitted', scope='scene',
                         owner='arrival', action='set', value=True)['kind'],
            'set_flag')
        with self.assertRaises(RuleError):
            state_effect(second.story, identifier='admitted', scope='scene',
                         owner='arrival', action='add', value=1)

    def test_legacy_jeanne_session_does_not_gain_new_flags(self):
        session = GameSession.new(self.content, self.legacy, 'main')
        self.assertEqual(session.narrative_state(), ())
        self.assertFalse(any(k.startswith('r42_')
                             for k in session.progress.story_flags))
        record = session.recording()
        self.assertEqual(GameSession.from_recording(record, self.content,
                                                    self.legacy).recording(), record)


if __name__ == '__main__':
    unittest.main()
