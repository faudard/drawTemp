"""Immutable, explicit rule composition. No global registration or plugin loading."""
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
class RuleSet:
    commands: Registry[CommandRule]
    effects: Registry[EffectRule]
    objectives: Registry[ObjectiveRule]
    behaviors: Registry[BehaviorRule]
    formulas: Registry[FormulaRule]
    version: str = '1'

    def with_family(self, family: str, registry: Registry):
        require(family in {'commands', 'effects', 'objectives', 'behaviors', 'formulas'}, 'Unknown rule family')
        return replace(self, **{family: registry})

    def manifest(self):
        return {'version': self.version, **{name: getattr(self, name).manifest()
                for name in ('commands', 'effects', 'objectives', 'behaviors', 'formulas')}}
