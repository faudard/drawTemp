"""Immutable, explicit rule composition. No global registration or plugin loading."""
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Callable, Generic, TypeVar

from ..model import require

T = TypeVar('T')


@dataclass(frozen=True)
class Registry(Generic[T]):
    entries: tuple[tuple[str, T], ...] = ()

    def __post_init__(self):
        object.__setattr__(self, 'entries', tuple((key, rule) for key, rule in self.entries))
        seen = set()
        for key, rule in self.entries:
            require(isinstance(key, str) and bool(key), 'Rule needs a non-empty id')
            require(key not in seen, f'Duplicate rule: {key}')
            require(isinstance(rule.version, str) and bool(rule.version), 'Rule needs a version')
            seen.add(key)

    def get(self, key: str) -> T:
        for name, rule in self.entries:
            if name == key:
                return rule
        require(False, f'Unknown or disabled rule: {key}')

    def __contains__(self, key):
        return any(name == key for name, _ in self.entries)

    def with_rule(self, key: str, rule: T, *, replace_existing=False):
        require(isinstance(key, str) and bool(key), 'Rule needs a non-empty id')
        require(isinstance(rule.version, str) and bool(rule.version), 'Rule needs a version')
        require(replace_existing or key not in self, f'Duplicate rule: {key}')
        return Registry(tuple((k, v) for k, v in self.entries if k != key) + ((key, rule),))

    def without(self, key: str):
        self.get(key)
        return Registry(tuple((k, v) for k, v in self.entries if k != key))

    def manifest(self):
        return {key: rule.version for key, rule in sorted(self.entries)}


@dataclass(frozen=True)
class CommandRule:
    execute: Callable
    version: str = '1'


@dataclass(frozen=True)
class EffectRule:
    apply: Callable
    amount: Callable
    area: bool = False
    version: str = '1'
    targets_downed: bool = False


@dataclass(frozen=True)
class ObjectiveRule:
    achieved: Callable
    needs_goal: bool = False
    needs_relic: bool = False
    version: str = '1'


@dataclass(frozen=True)
class BehaviorRule:
    choose: Callable
    version: str = '1'


@dataclass(frozen=True)
class FormulaRule:
    calculate: Callable
    version: str = '1'


@dataclass(frozen=True)
class StatusRule:
    beneficial: bool = False
    opposite: str = ''
    blocks: frozenset[str] = frozenset()
    interrupt: str = ''  # all / magic / none
    cancel_prepared: bool = False
    wake_on_damage: bool = False
    speed: Callable = lambda b, u, value: value
    mitigate: Callable = lambda b, u, skill, value: value
    end_turn: Callable = lambda b, u: None
    priority: int = 0
    version: str = '1'

    def __post_init__(self):
        object.__setattr__(self, 'blocks', frozenset(self.blocks))
        require(self.interrupt in {'', 'all', 'magic'}, 'Invalid status interruption policy')
        require(type(self.priority) is int, 'Status priority must be an integer')


@dataclass(frozen=True)
class MovementRule:
    bonus: int = 0
    ignore_height: bool = False
    teleport: bool = False
    after_move: Callable = lambda b, u: None
    version: str = '1'


@dataclass(frozen=True)
class ReactionRule:
    before_damage: Callable = lambda b, t, source, amount: False
    after_damage: Callable = lambda b, t, source, amount: None
    on_leave: Callable = lambda b, enemy, mover, previous, pursued: False
    forecast_leave: Callable = lambda b, enemy, mover, previous, seen: None
    evade: Callable = lambda b, target, chance: chance
    version: str = '1'


@dataclass(frozen=True)
class PreparationRule:
    validate: Callable
    covers: Callable = lambda b, watcher, cell: False
    enters: Callable = lambda b, watcher, previous, cell: False
    intercepts: Callable = lambda b, protector, prep, target: False
    displace: Callable = lambda b, target, caster, prep, amount: amount
    targeted: bool = False
    version: str = '1'


@dataclass(frozen=True)
class TacticRule:
    options: Callable
    arity: int = 2
    divisor: int = 2
    reposition: Callable = lambda b, u: []
    execute: Callable = lambda b, u, partner, cell: None
    version: str = '1'


    def __post_init__(self):
        require(type(self.arity) is int and self.arity in {2, 3}, 'Tactic arity must be 2 or 3')
        require(type(self.divisor) is int and self.divisor > 0, 'Tactic divisor must be positive')


@dataclass(frozen=True)
class TriggerConditionRule:
    matches: Callable
    validate: Callable
    version: str = '1'


@dataclass(frozen=True)
class TriggerActionRule:
    apply: Callable
    validate: Callable
    version: str = '1'
FAMILY_TYPES = {
    'commands': CommandRule, 'effects': EffectRule, 'objectives': ObjectiveRule,
    'behaviors': BehaviorRule, 'formulas': FormulaRule, 'statuses': StatusRule,
    'movements': MovementRule, 'reactions': ReactionRule, 'preparations': PreparationRule,
    'tactics': TacticRule, 'trigger_conditions': TriggerConditionRule, 'trigger_actions': TriggerActionRule,
}


@dataclass(frozen=True)
class RuleSet:
    commands: Registry[CommandRule]
    effects: Registry[EffectRule]
    objectives: Registry[ObjectiveRule]
    behaviors: Registry[BehaviorRule]
    formulas: Registry[FormulaRule]
    statuses: Registry[StatusRule]
    movements: Registry[MovementRule]
    reactions: Registry[ReactionRule]
    preparations: Registry[PreparationRule]
    tactics: Registry[TacticRule]
    trigger_conditions: Registry[TriggerConditionRule]
    trigger_actions: Registry[TriggerActionRule]
    version: str = '1'

    def __post_init__(self):
        for name, rule_type in FAMILY_TYPES.items():
            registry = getattr(self, name)
            require(isinstance(registry, Registry), f'{name}: expected a Registry')
            require(all(isinstance(rule, rule_type) for _, rule in registry.entries),
                    f'{name}: invalid rule descriptor type')

    def with_family(self, family: str, registry: Registry):
        require(family in FAMILY_TYPES, 'Unknown rule family')
        return replace(self, **{family: registry})

    def manifest(self):
        return {'version': self.version, **{name: getattr(self, name).manifest()
                for name in FAMILY_TYPES}}
