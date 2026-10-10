"""Integration tests for independently replaceable gameplay families."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from sporebound.ai import choose_command
from sporebound.campaign import Campaign
from sporebound.engine import Battle
from sporebound.model import Board, Content, Effect, Mission, RuleError, Skill, Tile, Unit
from sporebound.rules import (MovementRule, PreparationRule, ReactionRule, StatusRule,
                              TacticRule, TriggerActionRule, TriggerConditionRule, default_rules)


def content():
    return Content({'hit': Skill('hit', 'Hit', [Effect('damage', 2)], range=4)},
                   {'test': Mission('test', 'Test', Board(6, 3), [
                       Unit('hero', 'Hero', 'player', (0, 1), skills=['hit']),
                       Unit('wolf', 'Wolf', 'enemy', (4, 1))])})


def add(rules, family, key, rule):
    return rules.with_family(family, getattr(rules, family).with_rule(key, rule))


class ExtendedRuleTests(unittest.TestCase):
    def test_new_status_blocks_actions_and_runs_end_turn_hook(self):
        rules = add(default_rules(), 'statuses', 'meditating', StatusRule(
            blocks={'act', 'reaction'}, beneficial=True,
            end_turn=lambda b, u: b._heal(u, 3)))
        c = content()
        u = c.missions['test'].units[0]
        u.statuses = {'meditating': -1}
        u.hp = 20
        b = Battle(Content.from_dict(c.to_dict(), rules=rules), 'test', rules=rules)
        snapshot = b.recording()
        with self.assertRaises(RuleError):
            b.execute({'kind': 'act', 'skill': 'hit', 'cell': [4, 1]})
        self.assertEqual(b.recording(), snapshot)
        b.execute({'kind': 'end'})
        self.assertEqual(b.unit('hero').hp, 23)
        self.assertEqual(Battle.replay(b.recording(), rules=rules).digest(), b.digest())

    def test_status_modifier_order_and_removal_validation(self):
        rules = add(default_rules(), 'statuses', 'quick', StatusRule(
            speed=lambda b, u, n: n + 4, priority=-10))
        c = content()
        hero, wolf = c.missions['test'].units
        hero.statuses = {'haste': -1, 'quick': -1}
        wolf.ct = 90
        b = Battle(c, 'test', rules=rules)
        self.assertEqual(b.unit('hero').ct, 21)
        rules = rules.with_family('statuses', rules.statuses.without('quick'))
        with self.assertRaises(RuleError):
            Content.from_dict(c.to_dict(), rules=rules)

    def test_status_applied_by_skill_cancels_preparation(self):
        rules = add(default_rules(), 'statuses', 'daze', StatusRule(
            blocks={'reaction'}, cancel_prepared=True, wake_on_damage=True))
        c = content()
        c.skills['hit'].effects = [Effect('status', status='daze')]
        b = Battle(c, 'test', rules=rules)
        b.prepared_reactions['wolf'] = {'mode': 'guard', 'charges': 1, 'ct_tax': 20}
        b.execute({'kind': 'act', 'skill': 'hit', 'cell': [4, 1]})
        self.assertNotIn('wolf', b.prepared_reactions)
        self.assertIn('daze', b.unit('wolf').statuses)
        b._hurt(b.unit('wolf'), 1, reactions=False)
        self.assertNotIn('daze', b.unit('wolf').statuses)

    def test_custom_movement_reachability_and_completion(self):
        rules = add(default_rules(), 'movements', 'climber', MovementRule(
            bonus=2, ignore_height=True, after_move=lambda b, u: b.emit('climbed', unit=u.id)))
        c = content()
        c.missions['test'].units[0].movement = 'climber'
        c.missions['test'].units[0].move = 0
        c.missions['test'].board.tiles[(1, 1)] = Tile(height=5)
        b = Battle(c, 'test', rules=rules)
        before = b.digest()
        self.assertIn((1, 1), b.reachable())
        self.assertNotIn((3, 1), b.reachable())
        self.assertEqual(before, b.digest())
        b.execute({'kind': 'move', 'cell': [1, 1]})
        self.assertTrue(any(e['kind'] == 'climbed' for e in b.events))
        self.assertEqual(Battle.replay(b.recording(), rules=rules).digest(), b.digest())

    def test_custom_passive_absorbs_damage(self):
        def absorb(b, target, source, amount):
            b.emit('absorbed', unit=target.id, amount=amount)
            return True
        rules = add(default_rules(), 'reactions', 'shield', ReactionRule(before_damage=absorb))
        c = content()
        c.missions['test'].units[1].reaction = 'shield'
        b = Battle(c, 'test', rules=rules)
        b.execute({'kind': 'act', 'skill': 'hit', 'cell': [4, 1]})
        self.assertEqual(b.unit('wolf').hp, 40)
        self.assertTrue(any(e['kind'] == 'absorbed' for e in b.events))
        self.assertEqual(Battle.replay(b.recording(), rules=rules).digest(), b.digest())

    def test_custom_exit_reaction_forecast_and_execution(self):
        def leave(b, enemy, mover, previous, seen):
            b._hurt(mover, 2, enemy, reactions=False)
            return False
        rules = add(default_rules(), 'reactions', 'sting', ReactionRule(
            on_leave=leave, forecast_leave=lambda b, e, u, p, seen:
            {'kind': 'sting', 'unit': e.id, 'cell': p, 'chance': 1, 'amount': 2}))
        c = content()
        wolf = c.missions['test'].units[1]
        wolf.pos, wolf.reaction = (1, 1), 'sting'
        b = Battle(c, 'test', rules=rules)
        before = b.digest()
        self.assertEqual(b.movement_threats(b.active, [(0, 1), (0, 2)])[0]['amount'], 2)
        self.assertEqual(before, b.digest())
        b.execute({'kind': 'move', 'cell': [0, 2]})
        self.assertEqual(b.unit('hero').hp, 38)

    def test_custom_preparation_uses_same_entry_predicate(self):
        rules = add(default_rules(), 'preparations', 'watch', PreparationRule(
            validate=lambda b, u, target: None,
            covers=lambda b, w, cell: True,
            enters=lambda b, w, previous, cell: True))
        c = content()
        hero = c.missions['test'].units[0]
        hero.weapon, hero.attack_range = 'ranged', 5
        b = Battle(c, 'test', rules=rules)
        b.execute({'kind': 'prepare', 'mode': 'watch'})
        b.execute({'kind': 'end'})
        before = b.digest()
        rows = b.movement_threats(b.active, [(4, 1), (3, 1)])
        self.assertEqual(rows[0]['kind'], 'watch')
        self.assertEqual(before, b.digest())
        b.execute({'kind': 'move', 'cell': [3, 1]})
        self.assertTrue(any(e['kind'] == 'prepared_triggered' and e['mode'] == 'watch' for e in b.events))
        self.assertEqual(Battle.replay(b.recording(), rules=rules).digest(), b.digest())

    def test_removed_preparation_rejected_and_ai_falls_back(self):
        rules = default_rules()
        rules = rules.with_family('preparations', rules.preparations.without('overwatch').without('guard'))
        c = content()
        c.missions['test'].units[0].weapon = 'ranged'
        b = Battle(c, 'test', rules=rules)
        before = b.recording()
        with self.assertRaises(RuleError):
            b.execute({'kind': 'prepare', 'mode': 'overwatch'})
        self.assertEqual(before, b.recording())
        b.active.moved = True
        b.active.mp = 0
        self.assertNotEqual(choose_command(b).get('mode'), 'overwatch')

    def test_custom_tactic_forecast_execution_campaign_and_replay(self):
        def combo(b, caster, target):
            return [{'id': 'duet', 'partner': 'ally', 'target': target.id, 'ct_cost': 10}]
        rules = add(default_rules(), 'tactics', 'duet', TacticRule(combo, divisor=4))
        c = content()
        hero, wolf = c.missions['test'].units
        wolf.pos = (1, 1)
        hero.tactics = ['duet']
        c.missions['test'].units.append(Unit('ally', 'Ally', 'player', (2, 1), ct=30, tactics=['duet']))
        b = Battle(c, 'test', rules=rules)
        rows = b.forecast('attack', (1, 1))
        extra = next(r for r in rows if r['kind'] == 'tactic')
        self.assertEqual(extra['amount'], 3)
        b.execute({'kind': 'act', 'skill': 'attack', 'cell': [1, 1]})
        self.assertEqual(b.unit('wolf').hp, 22)
        self.assertEqual(Battle.replay(b.recording(), rules=rules).digest(), b.digest())
        campaign = Campaign(['test'])
        campaign.unlock_tactic('hero', 'ally', 'duet', ruleset=rules)
        campaign.prepare_tactic('hero', 'ally', 'duet', ruleset=rules)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'campaign.json'
            campaign.save(path)
            loaded = Campaign.load(path, ruleset=rules)
            prepared = loaded.prepare(c, 'test', ruleset=rules)
            self.assertIn('duet', prepared.unit('hero').tactics)
            with self.assertRaises(RuleError):
                Campaign.load(path)

    def test_custom_trigger_validates_and_fires_once(self):
        rules = add(default_rules(), 'trigger_conditions', 'moved', TriggerConditionRule(
            lambda b, t: b.unit('hero').pos == (1, 1), lambda ctx, t: None))
        rules = add(rules, 'trigger_actions', 'gold', TriggerActionRule(
            lambda b, a: setattr(b, 'loot', b.loot + a['amount']),
            lambda ctx, a: ctx.integer(a['amount'], 0, 99)))
        c = content()
        c.missions['test'].triggers = [{'id': 'reward', 'condition': 'moved',
                                       'actions': [{'kind': 'gold', 'amount': 7}]}]
        b = Battle(Content.from_dict(c.to_dict(), rules=rules), 'test', rules=rules)
        b.execute({'kind': 'move', 'cell': [1, 1]})
        b.execute({'kind': 'end'})
        self.assertEqual((b.loot, b.fired), (7, ['reward']))
        self.assertEqual(Battle.replay(b.recording(), rules=rules).digest(), b.digest())
        c.missions['test'].triggers[0]['actions'][0]['amount'] = -1
        with self.assertRaises(RuleError):
            Content.from_dict(c.to_dict(), rules=rules)

    def test_trigger_exception_restores_move_rng_and_fired_mark(self):
        def broken(b, action):
            b.rng.random()
            b.emit('broken')
            raise RuntimeError('trigger failed')
        rules = add(default_rules(), 'trigger_actions', 'broken', TriggerActionRule(broken, lambda c, a: None))
        c = content()
        c.missions['test'].triggers = [{'id': 'failure', 'condition': 'enter', 'pos': [1, 1],
                                       'actions': [{'kind': 'broken'}]}]
        b = Battle(c, 'test', rules=rules)
        before = b.recording()
        with self.assertRaises(RuntimeError):
            b.execute({'kind': 'move', 'cell': [1, 1]})
        self.assertEqual(before, b.recording())

    def test_v2_manifest_compatibility_requires_default_new_families(self):
        b = Battle(content(), 'test')
        old = b.recording()
        old['version'] = 2
        old['rules'] = {k: v for k, v in old['rules'].items()
                        if k in {'version', 'commands', 'effects', 'objectives', 'behaviors', 'formulas'}}
        self.assertEqual(Battle.replay(old).digest(), b.digest())
        rules = default_rules()
        rules = rules.with_family('statuses', rules.statuses.with_rule(
            'poison', replace(rules.statuses.get('poison'), version='2'), replace_existing=True))
        with self.assertRaisesRegex(RuleError, 'default extended rules'):
            Battle.replay(old, rules=rules)
        with self.assertRaisesRegex(RuleError, 'ruleset mismatch'):
            Battle.replay(b.recording(), rules=rules)

    def test_wrong_family_and_invalid_tactic_descriptor_rejected(self):
        rules = default_rules()
        with self.assertRaisesRegex(RuleError, 'descriptor type'):
            rules.with_family('statuses', rules.statuses.with_rule('bad', MovementRule()))
        with self.assertRaises(RuleError):
            TacticRule(lambda b, c, t: [], divisor=0)
