"""Public rule composition API. Build variants before constructing a battle."""
from .registry import BehaviorRule, CommandRule, EffectRule, FormulaRule, ObjectiveRule, Registry, RuleSet
from .commands import default_commands
from .effects import default_effects
from .objectives import default_objectives
from .combat import damage, hit_chance, _mitigate


def tactical_behavior(battle):
    from ..ai import _choose_tactical_command
    return _choose_tactical_command(battle)


def default_rules():
    return RuleSet(default_commands(), default_effects(), default_objectives(),
                   Registry((('tactical', BehaviorRule(tactical_behavior)),)),
                   Registry((('damage', FormulaRule(damage)), ('hit_chance', FormulaRule(hit_chance)),
                             ('mitigation', FormulaRule(_mitigate)))))
