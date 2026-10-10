"""Status lifecycle and ordered modifiers, with no hard-coded status dispatch."""
from .registry import Registry, StatusRule


def ordered(battle, unit):
    return sorted(((key, battle.rules.statuses.get(key)) for key in unit.statuses),
                  key=lambda pair: (pair[1].priority, pair[0]))


def blocked(battle, unit, action):
    return any(action in rule.blocks for _, rule in ordered(battle, unit))


def speed(battle, unit):
    value = unit.speed
    for _, rule in ordered(battle, unit):
        value = rule.speed(battle, unit, value)
    return value


def mitigate(battle, unit, skill, value):
    for _, rule in ordered(battle, unit):
        value = rule.mitigate(battle, unit, skill, value)
    return value


def end_turn(battle, unit):
    # Snapshot keys because a callback can remove statuses or down the actor.
    for key, rule in ordered(battle, unit):
        if key in unit.statuses and unit.alive:
            rule.end_turn(battle, unit)


def tick(battle, unit):
    for status in list(unit.statuses):
        if unit.statuses[status] > 0:
            unit.statuses[status] -= 1
            if unit.statuses[status] == 0:
                del unit.statuses[status]
                battle.emit('status_expired', unit=unit.id, status=status)


def wake(battle, unit):
    for key, rule in ordered(battle, unit):
        if rule.wake_on_damage:
            unit.statuses.pop(key, None)


def _status(battle, u, status, duration, source=None):
    rule = battle.rules.statuses.get(status)
    u.statuses.pop(rule.opposite, None)
    previous = u.statuses.get(status, 0)
    u.statuses[status] = -1 if previous == -1 or duration == -1 else max(duration, previous)
    if u.cast and (rule.interrupt == 'all' or rule.interrupt == 'magic'
                   and battle.content.skills[u.cast['skill']].magical):
        u.cast = None
        battle.emit('cast_cancelled', unit=u.id)
    if rule.cancel_prepared and u.id in battle.prepared_reactions:
        battle.prepared_reactions.pop(u.id, None)
        battle.emit('prepared_cancelled', unit=u.id, reason=status)
    battle.emit('status', unit=u.id, status=status, duration=duration,
                source=source.id if source else None)


def default_statuses():
    inactive = frozenset({'activation', 'reaction', 'continue_move', 'charge', 'evasion'})
    return Registry((
        ('poison', StatusRule(opposite='regen', end_turn=lambda b, u: b._hurt(u, max(1, u.max_hp // 8)), priority=0)),
        ('regen', StatusRule(beneficial=True, opposite='poison', end_turn=lambda b, u: b._heal(u, max(1, u.max_hp // 8)), priority=1)),
        ('haste', StatusRule(beneficial=True, opposite='slow', speed=lambda b, u, n: n * 3 // 2, priority=0)),
        ('slow', StatusRule(opposite='haste', speed=lambda b, u, n: max(1, n // 2), priority=1)),
        ('protect', StatusRule(beneficial=True, mitigate=lambda b, u, s, n: n if s.magical else n * 2 // 3)),
        ('shell', StatusRule(beneficial=True, mitigate=lambda b, u, s, n: n * 2 // 3 if s.magical else n)),
        ('guard', StatusRule(beneficial=True, mitigate=lambda b, u, s, n: n // 2, priority=10)),
        ('silence', StatusRule(blocks=frozenset({'magic'}), interrupt='magic')),
        ('sleep', StatusRule(blocks=inactive, interrupt='all', cancel_prepared=True, wake_on_damage=True)),
        ('stop', StatusRule(blocks=inactive, interrupt='all', cancel_prepared=True)),
        ('dont_move', StatusRule(blocks=frozenset({'move', 'continue_move', 'charge'}))),
        ('dont_act', StatusRule(blocks=frozenset({'act', 'reaction', 'charge'}), cancel_prepared=True)),
    ))
