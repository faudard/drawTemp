"""R42.B3 tests: canonical conditions, breakpoints and sandbox non-mutation."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.narrative_debugger_r42 import NarrativeDebugger
from sporebound.game_project import GameProject
from sporebound.model import RuleError
from sporebound.narrative_r42 import migrate_story_v1, set_dialogue_lines
from sporebound.narrative_state_r42 import (
    declare_state, state_condition, state_effect,
)


class NarrativeDebuggerR42Tests(unittest.TestCase):
    def setUp(self):
        self.content, original = reference_project()
        upgraded = migrate_story_v1(original, self.content)
        upgraded = set_dialogue_lines(upgraded, self.content, 'arrival', [
            {'id': 'a', 'speaker': 'Jeanne', 'text': 'Bonjour.'},
            {'id': 'b', 'speaker': 'Capitaine', 'text': 'Bonjour Jeanne.'},
        ])
        with_relation = declare_state(
            upgraded, self.content, identifier='captain',
            kind='relation', scope='campaign', owner='main', initial=40)
        when = state_condition(
            with_relation.story, identifier='captain',
            scope='campaign', owner='main', operator='gte', value=30)
        effect = state_effect(
            with_relation.story, identifier='captain',
            scope='campaign', owner='main', action='add', value=12)
        raw = with_relation.to_dict()
        choice = raw['story']['scenes'][0]['choices'][0]
        choice['when'] = {'all': [when, {'gold_gte': 0}]}
        choice['effects'] = [effect, {'kind': 'gold', 'amount': 7}]
        raw['story']['scenes'][0]['choices'].append(
            {'id': 'leave', 'label': 'Partir', 'when': {'not': when}})
        project = GameProject.from_dict(raw, self.content)
        self.editor = AuthoringSession.new(self.content, project)
        self.debugger = NarrativeDebugger(self.editor, 'main', seed=4)

    def test_conditions_are_observed_using_r9_and_project_not_modified(self):
        baseline = self.editor.snapshot().to_dict()
        report = self.debugger.report()
        self.assertTrue(report['isolated'])
        self.assertIsNone(report['replay_verified'])
        self.assertEqual(report['scene'], 'arrival')
        self.assertEqual(report['line']['index'], 0)
        detail = self.debugger.inspect()
        condition = next(r['condition'] for r in detail['choices']
                         if r['id'] == 'enter')
        self.assertTrue(condition['passed'])
        self.assertEqual([c['passed'] for c in condition['children']],
                         [True, True])
        denied = next(r for r in detail['choices'] if r['id'] == 'leave')
        self.assertFalse(denied['available'])
        self.debugger.step()
        self.assertEqual(self.debugger.report()['line']['index'], 1)
        self.assertEqual(self.editor.snapshot().to_dict(), baseline)

    def test_choice_breakpoint_stops_before_effects_then_steps_once(self):
        original = self.editor.snapshot().to_dict()
        self.debugger.breakpoint('arrival', 'enter')
        self.debugger.advance_line()
        before = self.debugger.report()
        paused = self.debugger.choose('enter')
        self.assertEqual(paused['revision'], before['revision'])
        self.assertEqual(paused['paused_on'], ['arrival', 'enter'])
        self.assertEqual(paused['gold'], 0)
        self.assertEqual(paused['history'], [])
        after = self.debugger.step()
        self.assertIsNone(after['paused_on'])
        self.assertEqual(after['gold'], 7)
        self.assertEqual(after['history'], [{'scene': 'arrival', 'choice': 'enter'}])
        self.assertEqual(after['flags']['r42_c_main_captain'], 52)
        self.assertEqual(after['scene'], '')
        last = after['events'][-1]
        self.assertEqual(last['gold_delta'], 7)
        self.assertEqual(last['history_delta'], 1)
        self.assertTrue(any(row['key'] == 'r42_c_main_captain'
                            and row['before'] == 40 and row['after'] == 52
                            for row in last['flags']))
        self.assertEqual(original, self.editor.snapshot().to_dict())
        with self.assertRaises(RuleError):
            self.debugger.step()

    def test_forecast_uses_canonical_choice_without_committing_anything(self):
        self.debugger.advance_line()
        report = self.debugger.report()
        preview = self.debugger.preview_choice('enter')
        self.assertFalse(preview['committed'])
        self.assertTrue(preview['isolated'])
        self.assertEqual(preview['gold_delta'], 7)
        self.assertEqual(preview['history_delta'], 1)
        self.assertTrue(any(row['key'] == 'r42_c_main_captain'
                            and row['after'] == 52 for row in preview['flags']))
        self.assertEqual(self.debugger.report(), report)
        with self.assertRaises(RuleError):
            self.debugger.preview_choice('leave')

    def test_locked_or_incomplete_choices_fail_without_mutation(self):
        before = self.debugger.report()
        with self.assertRaises(RuleError):
            self.debugger.choose('leave')
        with self.assertRaises(RuleError):
            self.debugger.choose('enter')
        with self.assertRaises(RuleError):
            self.debugger.breakpoint('not_scene', 'enter')
        self.assertEqual(self.debugger.report(), before)
        self.debugger.advance_line()
        with self.assertRaises(RuleError):
            self.debugger.choose('leave')
        self.assertEqual(self.debugger.report()['gold'], 0)

    def test_editor_revision_change_invalidates_old_debugger(self):
        baseline = self.editor.snapshot().to_dict()
        # Even undo/redo ABA must not reuse the same debugger context.
        self.editor.apply(self.editor.preview_project(
            lambda data: {**data, 'title': data['title'] + ' edition'},
            kind='test-edit'))
        with self.assertRaises(AuthoringError) as err:
            self.debugger.report()
        self.assertEqual(err.exception.code, 'stale_revision')
        self.editor.undo()
        self.assertEqual(self.editor.snapshot().to_dict()['project'],
                         baseline['project'])
        with self.assertRaises(AuthoringError):
            self.debugger.step()

    def test_breakpoint_budget_type_guards_and_inspection_fail_closed(self):
        with self.assertRaises(RuleError):
            self.debugger.breakpoint('arrival', 'enter', enabled=1)
        with self.assertRaises(RuleError):
            self.debugger.inspect('no_choice')
        with self.assertRaises(RuleError):
            self.debugger.choose('no_choice')
        self.debugger.breakpoint('arrival', 'enter')
        self.debugger.breakpoint('arrival', 'enter', False)
        self.assertEqual(self.debugger.report()['breakpoints'], [])


if __name__ == '__main__':
    unittest.main()
