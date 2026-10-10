"""Skill effects share execution and pure forecast contracts."""
from .registry import EffectRule, Registry


def damage(b, caster, target, skill, effect, cell):
    b._hurt(target, b.damage(caster, target, skill, effect), caster)


def heal(b, caster, target, skill, effect, cell):
    if target.alive:
        b._heal(target, effect.power)


def revive(b, caster, target, skill, effect, cell):
    if not target.alive and b.at(target.pos) is None and not b.board.tile(target.pos).blocked:
        target.hp = min(target.max_hp, max(1, effect.power))
        target.ct = 0
        b.emit('revive', unit=target.id, source=caster.id)


def status(b, caster, target, skill, effect, cell):
    if target.alive:
        b._status(target, effect.status, effect.duration, caster)


def cleanse(b, caster, target, skill, effect, cell):
    target.statuses.pop(effect.status, None)


def mp(b, caster, target, skill, effect, cell):
    target.mp = min(target.max_mp, target.mp + effect.power)


def displace(b, caster, target, skill, effect, cell):
    if target.alive:
        b._displace(caster, target, effect.power, effect.kind == 'pull')


def zone(b, caster, target, skill, effect, cell):
    b.zones.append({'cells': sorted(b._area(cell, skill)), 'remaining': effect.duration,
                    'power': effect.power, 'team': caster.team, 'scope': effect.scope})


def power(b, caster, target, skill, effect):
    return effect.power


def default_effects():
    return Registry(tuple((key, EffectRule(apply, amount, area, targets_downed=key == 'revive')) for key, apply, amount, area in (
        ('damage', damage, lambda b, c, t, s, e: b.damage(c, t, s, e), False),
        ('heal', heal, lambda b, c, t, s, e: min(e.power, t.max_hp - t.hp), False),
        ('revive', revive, power, False),
        ('status', status, power, False),
        ('cleanse', cleanse, power, False),
        ('mp', mp, lambda b, c, t, s, e: min(e.power, t.max_mp - t.mp), False),
        ('push', displace, power, False), ('pull', displace, power, False),
        ('zone', zone, power, True),
    )))
