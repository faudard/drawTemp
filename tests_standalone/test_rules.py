"""Extension contracts exercised through real battles, not registry-only mocks."""
from pathlib import Path
import tempfile
import unittest

from sporebound.actors import ActorFactory
from sporebound.ai import choose_command
from sporebound.engine import Battle
from sporebound.model import Board, Content, Effect, Mission, RuleError, Skill, Unit
from sporebound.rules import (BehaviorRule, CommandRule, EffectRule, FormulaRule,
                              ObjectiveRule, default_rules)
from sporebound.storage import load_battle, save_battle


def content():
    return Content({'hit': Skill('hit', 'Hit', [Effect('damage', 2)], range=4)},
                   {'test': Mission('test', 'Test', Board(5, 3), [
                       Unit('hero', 'Hero', 'player', (0, 1), skills=['hit']),
                       Unit('wolf', 'Wolf', 'enemy', (2, 1))])})


class RuleTests(unittest.TestCase):
    def test_custom_effect_forecast_execution_and_saved_replay(self):
        def apply(b, c, t, s, e, cell):
            b._hurt(t, 7, c)
        rules = default_rules()
        rules = rules.with_family('effects', rules.effects.with_rule(
            'fixed', EffectRule(apply, lambda *args: 7, version='2')))
        data = content().to_dict()
        data['skills'][0]['effects'][0]['kind'] = 'fixed'
        c = Content.from_dict(data, rules=rules)
        b = Battle(c, 'test', rules=rules)
        before = b.digest()
        self.assertEqual(b.forecast('hit', (2, 1))[0]['amount'], 7)
        self.assertEqual(before, b.digest())
        b.execute({'kind': 'act', 'skill': 'hit', 'cell': [2, 1]})
        self.assertEqual(b.unit('wolf').hp, 33)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'battle.json'
            save_battle(path, b)
            self.assertEqual(load_battle(path, rules=rules).digest(), b.digest())
            with self.assertRaisesRegex(RuleError, 'ruleset mismatch'):
                load_battle(path)

    def test_rule_removal_validates_content_and_rejects_commands(self):
        rules = default_rules()
        no_damage = rules.with_family('effects', rules.effects.without('damage'))
        with self.assertRaises(RuleError):
            Battle(content(), 'test', rules=no_damage)
        no_move = rules.with_family('commands', rules.commands.without('move'))
        b = Battle(content(), 'test', rules=no_move)
        before = b.recording()
        with self.assertRaisesRegex(RuleError, 'disabled rule'):
            b.execute({'kind': 'move', 'cell': [1, 1]})
        self.assertEqual(b.recording(), before)
        self.assertIn('move', rules.commands)
        self.assertNotEqual(choose_command(b)['kind'], 'move')

    def test_custom_command_rolls_back_unexpected_exception(self):
        def broken(b, u, command):
            u.hp = 1
            b.rng.random()
            b.emit('broken')
            b.loot = 999
            raise RuntimeError('extension bug')
        rules = default_rules()
        rules = rules.with_family('commands', rules.commands.with_rule('broken', CommandRule(broken)))
        b = Battle(content(), 'test', rules=rules)
        before = b.recording()
        with self.assertRaisesRegex(RuntimeError, 'extension bug'):
            b.execute({'kind': 'broken'})
        self.assertEqual(before, b.recording())

    def test_replace_formula_and_version_guard(self):
        rules = default_rules()
        with self.assertRaisesRegex(RuleError, 'Duplicate rule'):
            rules.formulas.with_rule('damage', FormulaRule(lambda *args: 3))
        rules = rules.with_family('formulas', rules.formulas.with_rule(
            'damage', FormulaRule(lambda *args: 3, version='flat-3'), replace_existing=True))
        b = Battle(content(), 'test', rules=rules)
        self.assertEqual(b.forecast('hit', (2, 1))[0]['amount'], 3)
        b.execute({'kind': 'act', 'skill': 'hit', 'cell': [2, 1]})
        self.assertEqual(b.unit('wolf').hp, 37)
        self.assertEqual(Battle.replay(b.recording(), rules=rules).digest(), b.digest())
        changed = rules.with_family('formulas', rules.formulas.with_rule(
            'damage', FormulaRule(lambda *args: 3, version='flat-3-v2'), replace_existing=True))
        with self.assertRaisesRegex(RuleError, 'ruleset mismatch'):
            Battle.replay(b.recording(), rules=changed)

    def test_custom_objective_and_behavior(self):
        rules = default_rules()
        rules = rules.with_family('objectives', rules.objectives.with_rule(
            'patient', ObjectiveRule(lambda b: b.tick >= 11)))
        rules = rules.with_family('behaviors', rules.behaviors.with_rule(
            'idle', BehaviorRule(lambda b: {'kind': 'end'})))
        c = content()
        c.missions['test'].objective = 'patient'
        for actor in c.missions['test'].units:
            actor.behavior = 'idle'
        b = Battle(Content.from_dict(c.to_dict(), rules=rules), 'test', rules=rules)
        for _ in range(2):
            b.execute(choose_command(b))
        self.assertEqual(b.result, 'victory')
        self.assertEqual(Battle.replay(b.recording(), rules=rules).digest(), b.digest())

    def test_legacy_recording_without_manifest(self):
        b = Battle(content(), 'test')
        b.execute({'kind': 'end'})
        recording = b.recording()
        recording['version'] = 1
        del recording['rules']
        for mission in recording['content']['missions']:
            for unit in mission['units']:
                for key in ('archetype', 'kind', 'tags', 'behavior'):
                    unit.pop(key)
        self.assertEqual(Battle.replay(recording).digest(), b.digest())


class ActorTests(unittest.TestCase):
    def test_templates_isolated_and_round_trip(self):
        data = content().to_dict()
        data['archetypes'] = {'wolf': {'kind': 'monster', 'max_hp': 60, 'attack': 9,
                                      'skills': ['hit'], 'tags': ['beast']}}
        data['missions'][0]['units'][1] = {'id': 'wolf', 'name': 'Wolf', 'team': 'enemy',
                                          'pos': [2, 1], 'archetype': 'wolf', 'attack': 12}
        c = Content.from_dict(data)
        wolf = c.missions['test'].units[1]
        self.assertEqual((wolf.hp, wolf.max_hp, wolf.attack, wolf.kind), (60, 60, 12, 'monster'))
        self.assertEqual(Content.from_dict(c.to_dict()).to_dict(), c.to_dict())
        b = Battle(c, 'test')
        b.unit('wolf').tags.append('wounded')
        self.assertEqual(wolf.tags, ['beast'])
        self.assertEqual(c.archetypes['wolf']['tags'], ['beast'])
        other = ActorFactory(c.archetypes).create({'id': 'pet', 'name': 'Pet', 'team': 'player',
                                                  'pos': [1, 1], 'archetype': 'wolf'})
        self.assertEqual((other.team, other.kind), ('player', 'monster'))

    def test_invalid_and_unused_templates_rejected(self):
        for template in ({'max_hp': -1}, {'skills': ['missing']}, {'behavior': 'missing'},
                         {'kind': 'invalid'}, {'ct': 100}, {'tags': ['beast', 'beast']}):
            data = content().to_dict()
            data['archetypes'] = {'invalid': template}
            with self.subTest(template=template), self.assertRaises(RuleError):
                Content.from_dict(data)
        data = content().to_dict()
        data['missions'][0]['units'][1]['archetype'] = 'missing'
        with self.assertRaises(RuleError):
            Content.from_dict(data)

    def test_templates_do_not_require_unrelated_default_policies(self):
        rules = default_rules()
        rules = rules.with_family('objectives', rules.objectives.without('eliminate'))
        rules = rules.with_family('behaviors', rules.behaviors.without('tactical').with_rule(
            'idle', BehaviorRule(lambda b: {'kind': 'end'})))
        data = content().to_dict()
        data['archetypes'] = {'custom': {'kind': 'monster', 'behavior': 'idle'}}
        data['missions'][0]['objective'] = 'survive'
        for actor in data['missions'][0]['units']:
            actor['behavior'] = 'idle'
        self.assertIn('custom', Content.from_dict(data, rules=rules).archetypes)
