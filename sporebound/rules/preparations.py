"""Prepared reactions share eligibility and path forecasts with execution."""
from ..model import distance, require
from .registry import PreparationRule, Registry


def validate_overwatch(b, u, target):
    require(u.weapon == 'ranged', 'Overwatch requires a ranged weapon')
    require(not b.engaged_by(u), 'Cannot prepare Overwatch while engaged')


def validate_close(b, u, target):
    require(b.engagement_range(u) > 0, 'Preparation requires a close-combat control zone')


def validate_intercept(b, u, target_id):
    validate_close(b, u, target_id)
    require(target_id is not None, 'Intercept needs a protected ally')
    require(any(t.id == target_id for t in b.units), 'Unknown Intercept target')
    target = b.unit(target_id)
    require(target.alive and target.team == u.team and target.id != u.id, 'Invalid Intercept target')
    require(distance(u.pos, target.pos) <= max(1, b.engagement_range(u))
            and b.line_of_sight(u.pos, target.pos), 'Intercept target outside protection range')


def ranged_covers(b, watcher, cell):
    skill = b._basic(watcher)
    return skill.min_range <= distance(watcher.pos, cell) <= skill.range and b.line_of_sight(watcher.pos, cell)


def guard_covers(b, watcher, cell):
    radius = b.engagement_range(watcher)
    return radius > 0 and distance(watcher.pos, cell) <= radius


def guard_enters(b, watcher, previous, cell):
    return not guard_covers(b, watcher, previous) and guard_covers(b, watcher, cell)


def intercepts(b, protector, prep, target):
    return (prep.get('target') == target.id and protector.alive and protector.team == target.team
            and b._can_react(protector)
            and distance(protector.pos, target.pos) <= max(1, b.engagement_range(protector))
            and b.line_of_sight(protector.pos, target.pos))


def brace(b, target, caster, prep, amount):
    if prep.get('charges', 0) <= 0:
        return amount
    absorbed = min(amount, 2)
    prep['charges'] -= 1
    target.ct = max(0, target.ct - prep.get('ct_tax', 20))
    b.emit('brace', unit=target.id, source=caster.id, absorbed=absorbed)
    if prep['charges'] <= 0:
        b.prepared_reactions.pop(target.id, None)
    return amount - absorbed


def default_preparations():
    return Registry((
        ('overwatch', PreparationRule(validate_overwatch, covers=ranged_covers,
                                     enters=lambda b, w, previous, cell: ranged_covers(b, w, cell))),
        ('guard', PreparationRule(validate_close, covers=guard_covers, enters=guard_enters)),
        ('brace', PreparationRule(validate_close, displace=brace)),
        ('intercept', PreparationRule(validate_intercept, intercepts=intercepts, targeted=True)),
    ))
