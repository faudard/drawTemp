"""Passive reactions: damage hooks, exit reactions and their pure forecasts."""
from copy import deepcopy
from ..model import distance
from .registry import ReactionRule, Registry


def mp_switch(b, target, source, amount):
    if target.mp > 0 and b.rng.randrange(100) < target.brave:
        target.mp = max(0, target.mp - amount)
        b.emit('mp_switch', unit=target.id, amount=amount)
        return True
    return False


def auto_potion(b, target, source, amount):
    if b.inventory[target.team]['potion'] > 0 and b.rng.randrange(100) < target.brave:
        b.inventory[target.team]['potion'] -= 1
        b._heal(target, 25)


def counter(b, target, source, amount):
    if source.alive and b.rng.randrange(100) < target.brave:
        skill = b._basic(target)
        if skill.min_range <= distance(target.pos, source.pos) <= skill.range and b.line_of_sight(target.pos, source.pos):
            if b.rng.random() < b.hit_chance(target, source, skill):
                b._hurt(source, b.damage(target, source, skill, skill.effects[0]), target, reactions=False)
                b.emit('counter', unit=target.id, target=source.id)


def opportunity(b, enemy, mover, previous, pursued):
    if not mover.disengaging and b.rng.randrange(100) < enemy.brave:
        skill = b._basic(enemy)
        if b.rng.random() < b.hit_chance(enemy, mover, skill):
            b._hurt(mover, b.damage(enemy, mover, skill, skill.effects[0]), enemy, reactions=False)
    return False


def forecast_opportunity(b, enemy, mover, previous, seen):
    if mover.disengaging or not b._can_react(enemy):
        return None
    skill = b._basic(enemy)
    ghost = deepcopy(mover)
    ghost.pos = previous
    if skill.min_range <= distance(enemy.pos, previous) <= skill.range and b.line_of_sight(enemy.pos, previous):
        return {'kind': 'opportunity', 'unit': enemy.id, 'cell': previous,
                'chance': enemy.brave / 100 * b.hit_chance(enemy, ghost, skill),
                'amount': b.damage(enemy, ghost, skill, skill.effects[0])}


def can_pursue(b, enemy, previous, seen):
    return (enemy.id not in seen and b._can_react(enemy) and distance(enemy.pos, previous) == 1
            and not b.board.tile(previous).blocked and b.can_step_height(enemy, enemy.pos, previous))


def pursuit(b, enemy, mover, previous, pursued):
    return can_pursue(b, enemy, previous, pursued) and b.rng.randrange(100) < enemy.brave


def forecast_pursuit(b, enemy, mover, previous, seen):
    if can_pursue(b, enemy, previous, seen):
        seen.add(enemy.id)
        return {'kind': 'pursuit', 'unit': enemy.id, 'cell': previous, 'chance': enemy.brave / 100, 'amount': 0}


def default_reactions():
    return Registry((
        ('none', ReactionRule()), ('mp_switch', ReactionRule(before_damage=mp_switch)),
        ('auto_potion', ReactionRule(after_damage=auto_potion)),
        ('counter', ReactionRule(after_damage=counter)),
        ('opportunity', ReactionRule(on_leave=opportunity, forecast_leave=forecast_opportunity)),
        ('pursuit', ReactionRule(on_leave=pursuit, forecast_leave=forecast_pursuit)),
        ('blade_grasp', ReactionRule(evade=lambda b, t, chance: chance * (1 - t.brave / 100) if b._can_react(t) else chance)),
    ))
