"""Run from the repository: python -m examples.modular_rules."""
from sporebound.ai import simulate
from sporebound.engine import Battle
from sporebound.model import Content
from sporebound.rules import FormulaRule, MovementRule, StatusRule, default_rules


def flat_damage(battle, caster, target, skill, effect):
    return 8


def main():
    rules = default_rules()
    rules = rules.with_family('commands', rules.commands.without('charge'))
    rules = rules.with_family('formulas', rules.formulas.with_rule(
        'damage', FormulaRule(flat_damage, version='example-flat-8-v1'), replace_existing=True))
    rules = rules.with_family('movements', rules.movements.with_rule(
        'climber', MovementRule(bonus=1, ignore_height=True)))
    rules = rules.with_family('statuses', rules.statuses.with_rule(
        'vitality', StatusRule(beneficial=True, end_turn=lambda b, u: b._heal(u, 2))))
    content = Content.from_dict({
        'version': 1,
        'skills': [],
        'archetypes': {
            'knight': {'kind': 'character', 'max_hp': 48, 'defense': 3, 'tags': ['humanoid']},
            'wolf': {'kind': 'monster', 'max_hp': 32, 'speed': 12, 'tags': ['beast'],
                     'behavior': 'tactical', 'movement': 'climber'},
        },
        'missions': [{
            'id': 'duel', 'name': 'Knight and wolf', 'board': {'width': 5, 'height': 3},
            'units': [
                {'id': 'hero', 'name': 'Knight', 'archetype': 'knight', 'team': 'player', 'pos': [0, 1], 'statuses': {'vitality': -1}},
                {'id': 'wolf', 'name': 'Wolf', 'archetype': 'wolf', 'team': 'enemy', 'pos': [4, 1]},
            ],
        }],
    }, rules=rules)
    battle = Battle(content, 'duel', seed=7, rules=rules)
    print(simulate(battle))
    assert Battle.replay(battle.recording(), rules=rules).digest() == battle.digest()


if __name__ == '__main__':
    main()
