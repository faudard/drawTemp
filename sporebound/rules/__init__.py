"""Public rule composition API. Build variants before constructing a battle."""
from .registry import (BehaviorRule, CommandRule, EffectRule, FormulaRule, ObjectiveRule,
                       Registry, RuleSet, StatusRule, MovementRule, ReactionRule,
                       PreparationRule, TacticRule, TriggerConditionRule, TriggerActionRule)
from .commands import default_commands
from .effects import default_effects
from .objectives import default_objectives
from .combat import damage, hit_chance, _mitigate
from .statuses import default_statuses
from .movement import default_movements
from .passives import default_reactions
from .preparations import default_preparations
from .tactics import default_tactics
from .triggers import default_trigger_conditions, default_trigger_actions


def tactical_behavior(battle):
    actor = battle.active
    if actor is not None and actor.patrol_route:
        return patrol_behavior(battle)
    from ..ai import _choose_tactical_command
    return _choose_tactical_command(battle)


def patrol_behavior(battle):
    """Follow the nearest route waypoint until a player enters sight."""
    from ..ai import _choose_tactical_command
    from ..model import distance

    actor = battle.active
    if actor is None or len(actor.patrol_route) < 2:
        return _choose_tactical_command(battle)
    seen = any(player.alive and player.team == 'player'
               and distance(actor.pos, player.pos) <= 5
               and battle.line_of_sight(actor.pos, player.pos)
               for player in battle.units)
    if seen:
        return _choose_tactical_command(battle)
    if actor.moved or actor.cast or battle.status_blocks(actor, 'move'):
        return {'kind': 'end'}

    route = [tuple(cell) for cell in actor.patrol_route]
    current = min(range(len(route)),
                  key=lambda index: (distance(actor.pos, route[index]), index))
    target = route[(current + 1) % len(route)]
    before = distance(actor.pos, target)
    reachable = battle.reachable(actor) if 'move' in battle.rules.commands else {}
    options = [(distance(cell, target), cost, cell)
               for cell, (cost, _path) in reachable.items()
               if cell != actor.pos and distance(cell, target) < before]
    if options:
        destination = min(options)[2]
        return {'kind': 'move', 'cell': list(destination)}

    dx, dy = target[0] - actor.pos[0], target[1] - actor.pos[1]
    facing = (1 if dx > 0 else -1, 0) if abs(dx) > abs(dy) else (0, 1 if dy > 0 else -1)
    return {'kind': 'end', 'facing': list(facing)}


def default_rules():
    return RuleSet(default_commands(), default_effects(), default_objectives(),
                   Registry((('tactical', BehaviorRule(tactical_behavior)),)),
                   Registry((('damage', FormulaRule(damage)), ('hit_chance', FormulaRule(hit_chance)),
                             ('mitigation', FormulaRule(_mitigate)))),
                   default_statuses(), default_movements(), default_reactions(),
                   default_preparations(), default_tactics(), default_trigger_conditions(),
                   default_trigger_actions())
