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
    from ..ai import _choose_tactical_command
    return _choose_tactical_command(battle)


def default_rules():
    return RuleSet(default_commands(), default_effects(), default_objectives(),
                   Registry((('tactical', BehaviorRule(tactical_behavior)),)),
                   Registry((('damage', FormulaRule(damage)), ('hit_chance', FormulaRule(hit_chance)),
                             ('mitigation', FormulaRule(_mitigate)))),
                   default_statuses(), default_movements(), default_reactions(),
                   default_preparations(), default_tactics(), default_trigger_conditions(),
                   default_trigger_actions())
