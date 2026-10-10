"""2.5.2 narrative condition builder and choice-runtime parity tests."""
from copy import deepcopy
from pathlib import Path
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.campaign import Campaign
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.narrative import StoryBook
from sporebound import story_authoring
from sporebound.story_conditions import (change_choice, evaluate, predicate,
                                        rows, typed_value, update_expression)


class ConditionStudioTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.load(Path(DEFAULT_CONTENT).with_suffix('.game.json'),
                                        self.content)
        self.project = story_authoring.create_scene(
            self.project, self.content, 'conditions_test',
            'Contrôle du camp', 'Quel chemin ?', 'Capitaine')
        self.project = story_authoring.add_choice(
            self.project, self.content, 'conditions_test', 'secret',
            'Chemin caché', when={'flag': 'trust', 'gte': 2})
        self.before = deepcopy(self.project.to_dict())

    def _when(self, project, choice='secret'):
        scene = next(s for s in project.story['scenes'] if s['id'] == 'conditions_test')
        result = next(c for c in scene['choices'] if c['id'] == choice)
        return result.get('when')

    def test_condition_builder_and_or_not_nested_with_stable_paths(self):
        start = self._when(self.project)
        expression = update_expression(start, 'wrap', operator='all')
        self.assertEqual(rows(expression)[0]['kind'], 'all')
        mission = predicate('completed_mission', 'garden', content=self.content)
        expression = update_expression(expression, 'append', leaf=mission)
        expr = update_expression(expression, 'wrap', path=(('all', 1),),
                                 operator='not')
        expression = update_expression(expr, 'wrap', path=(('all', 0),),
                                       operator='any')
        expression = update_expression(expression, 'append',
                                       path=(('all', 0),),
                                       leaf=predicate('gold_gte', value='50',
                                                      content=self.content))
        found = rows(expression)
        self.assertEqual(len(found), 6)
        self.assertEqual(found[-1]['kind'], 'completed_mission')
        self.assertEqual(found[-2]['kind'], 'not')
        self.assertEqual(found[0]['path'], ())
        self.assertEqual(found[3]['path'],
                         (('all', 0), ('any', 1)))
        updated = change_choice(self.project, self.content,
                                'conditions_test', 'secret', expression)
        self.assertEqual(self._when(updated), expression)
        self.assertEqual(self.project.to_dict(), self.before)

    def test_replace_and_delete_are_atomic_and_cannot_erase_fallback(self):
        start = self._when(self.project)
        edited = update_expression(start, 'replace', leaf=predicate(
            'flag_eq', 'trust', 'true', content=self.content))
        self.assertIs(self._when(change_choice(self.project, self.content,
                         'conditions_test', 'secret', edited))['eq'], True)
        with self.assertRaises(RuleError):
            change_choice(self.project, self.content,
                          'conditions_test', 'continue',
                          {'flag': 'banned', 'eq': True})
        self.assertEqual(self.project.to_dict(), self.before)
        cleared = update_expression(start, 'delete')
        self.assertIsNone(cleared)
        self.assertNotIn('when', next(c for s in change_choice(
            self.project, self.content, 'conditions_test', 'secret', cleared
        ).story['scenes'] if s['id'] == 'conditions_test'
            for c in s['choices'] if c['id'] == 'secret'))

    def test_reject_invalid_paths_and_structurally_empty_groups(self):
        root = update_expression(self._when(self.project), 'wrap', operator='any')
        root = update_expression(root, 'append',
                                 leaf=predicate('gold_gte', value='25'))
        before = deepcopy(root)
        for path in ((('any', 9),), ('not',), (('all', 0),)):
            with self.subTest(path=path), self.assertRaises(RuleError):
                update_expression(root, 'replace', path=path,
                                  leaf=predicate('gold_gte', value='0'))
            self.assertEqual(root, before)
        singleton = update_expression(self._when(self.project),
                                      'wrap', operator='all')
        with self.assertRaises(RuleError):
            update_expression(singleton, 'delete', path=(('all', 0),))
        with self.assertRaises(RuleError):
            update_expression(root, 'delete', path=('not',))

    def test_safe_scalar_types_and_preview_match_real_storybook(self):
        self.assertIs(typed_value('true'), True)
        self.assertIs(typed_value('false'), False)
        self.assertEqual(typed_value(' -12 '), -12)
        self.assertEqual(typed_value('covenant'), 'covenant')
        with self.assertRaises(RuleError):
            predicate('flag_gte', 'trust', 'not-a-number', content=self.content)
        with self.assertRaises(RuleError):
            predicate('completed_mission', 'unknown', content=self.content)
        with self.assertRaises(RuleError):
            predicate('gold_gte', value='-1', content=self.content)

        expr = {'all': [{'flag': 'trust', 'gte': 2},
                        {'not': {'completed_mission': 'garden'}}]}
        for flags, completed in (({'trust': 2}, []),
                                 ({'trust': True}, []),
                                 ({'trust': 2}, ['garden'])):
            expected = evaluate(expr, flags=flags, completed=completed)
            from types import SimpleNamespace
            from sporebound.narrative import matches
            self.assertEqual(expected, matches(expr, SimpleNamespace(
                story_flags=flags, gold=0, completed=completed)))
        self.assertTrue(evaluate(expr, flags={'trust': 2}))
        self.assertFalse(evaluate(expr, flags={'trust': True}))

    def test_runtime_routing_uses_newly_authored_condition_without_schema_change(self):
        when = update_expression(self._when(self.project), 'wrap',
                                 operator='all')
        when = update_expression(when, 'append',
                                 leaf=predicate('gold_gte', value='25'))
        project = change_choice(self.project, self.content,
                                'conditions_test', 'secret', when)
        book = StoryBook(project.story, self.content, project.campaigns)
        progress = project.new_game('main', self.content)
        progress.story_pending = 'conditions_test'
        progress.story_flags['trust'] = 3
        progress.gold = 10
        self.assertEqual([c['id'] for c in book.choices(progress)], ['continue'])
        progress.gold = 25
        self.assertEqual([c['id'] for c in book.choices(progress)],
                         ['continue', 'secret'])
        self.assertEqual(project.story['scenes'][-1]['id'], 'conditions_test')


if __name__ == '__main__':
    unittest.main()
