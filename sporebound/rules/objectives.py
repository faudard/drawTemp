"""Victory policies; defeat/protected-unit invariants remain in Battle."""
from .registry import ObjectiveRule, Registry


def default_objectives():
    return Registry((
        ('eliminate', ObjectiveRule(lambda b: not any(u.alive and u.team == 'enemy' for u in b.units))),
        ('survive', ObjectiveRule(lambda b: b.tick >= b.mission.target_ticks)),
        ('extract', ObjectiveRule(lambda b: any(u.alive and u.team == 'player' and u.pos in b.mission.goal for u in b.units), needs_goal=True)),
        ('hold', ObjectiveRule(lambda b: b.hold_ticks >= b.mission.target_ticks, needs_goal=True)),
        ('crown', ObjectiveRule(lambda b: bool(b.carrier) and b.unit(b.carrier).pos in b.mission.goal, needs_goal=True, needs_relic=True)),
    ))
