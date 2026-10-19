"""R31.F: opted-in battle-scoped typed variables backed by the Battle journal.

No parallel save payload: every state write is an authenticated Battle event
produced by the canonical R9 trigger dispatcher. Replays reconstruct variables
through the original command stream and checksum. Campaign.story_flags is a
separate scope and is deliberately never changed by these tactical rules.
"""
from __future__ import annotations

import re

from .model import require
from .rules.registry import TriggerActionRule, TriggerConditionRule

_VARIABLE = re.compile(r"r31_[a-z][a-z0-9_]{0,39}\Z")
MIN_VALUE, MAX_VALUE = -1000000, 1000000
MAX_VARIABLES = 32
MAX_JOURNAL_WRITES = 4096


def _name(row):
    name = row.get("name")
    require(type(name) is str and _VARIABLE.fullmatch(name) is not None,
            "Logic variable name must match r31_[a-z][a-z0-9_]* (<=44 chars)")


def _scalar(value):
    require(type(value) is bool or (type(value) is int and
            MIN_VALUE <= value <= MAX_VALUE),
            "Logic variable requires a Boolean or integer in -1000000..1000000")


def validate_set(_context, action):
    require(type(action) is dict and set(action) == {"kind", "name", "value"},
            "Malformed typed variable assignment")
    _name(action)
    _scalar(action["value"])


def validate_add(_context, action):
    require(type(action) is dict and set(action) == {"kind", "name", "amount"},
            "Malformed typed variable increment")
    _name(action)
    require(type(action["amount"]) is int and -10000 <= action["amount"] <= 10000
            and action["amount"] != 0,
            "Logic increment must be a non-zero integer in -10000..10000")


def validate_compare(_context, condition):
    require(type(condition) is dict and
            set(condition) == {"condition", "name", "operator", "value"},
            "Malformed typed variable comparison")
    _name(condition)
    require(condition["operator"] in ("eq", "ne", "gte", "lte"),
            "Unsupported variable comparison")
    _scalar(condition["value"])
    require(condition["operator"] in ("eq", "ne") or
            type(condition["value"]) is int,
            "Only numeric variables support >= and <=")


def variables_from_journal(battle):
    """Detached bounded state projection; never trust an editor-owned cache."""
    current = {}
    count = 0
    for row in battle.events:
        if row["kind"] != "logic_variable":
            continue
        count += 1
        require(count <= MAX_JOURNAL_WRITES, "Logic variable journal budget exceeded")
        name = row["name"]
        value = row["value"]
        require(type(name) is str and _VARIABLE.fullmatch(name) is not None,
                "Invalid recorded variable name")
        _scalar(value)
        if name not in current:
            require(len(current) < MAX_VARIABLES,
                    "Logic variable count exceeded")
        current[name] = value
    return current


def set_variable(battle, action):
    state = variables_from_journal(battle)
    name, value = action["name"], action["value"]
    require(name in state or len(state) < MAX_VARIABLES,
            "Logic variable count exceeded")
    battle.emit("logic_variable", name=name, value=value)


def add_variable(battle, action):
    state = variables_from_journal(battle)
    name = action["name"]
    previous = state.get(name, 0)
    require(type(previous) is int,
            "Cannot increment a Boolean variable")
    value = previous + action["amount"]
    _scalar(value)
    require(name in state or len(state) < MAX_VARIABLES,
            "Logic variable count exceeded")
    battle.emit("logic_variable", name=name, value=value)


def compare_variable(battle, condition):
    state = variables_from_journal(battle)
    value = state.get(condition["name"])
    if value is None:
        return False
    other = condition["value"]
    if type(value) is not type(other):
        return False
    op = condition["operator"]
    return {"eq": lambda: value == other, "ne": lambda: value != other,
            "gte": lambda: value >= other, "lte": lambda: value <= other}[op]()


def install_logic_variable_rules(rules):
    """Explicit immutable family composition for authored R31.F content only."""
    actions = rules.trigger_actions
    conditions = rules.trigger_conditions
    if "logic_set" not in actions:
        actions = actions.with_rule(
            "logic_set", TriggerActionRule(set_variable, validate_set,
                                           version="5.0-r31f"))
        actions = actions.with_rule(
            "logic_add", TriggerActionRule(add_variable, validate_add,
                                           version="5.0-r31f"))
    if "logic_compare" not in conditions:
        conditions = conditions.with_rule(
            "logic_compare", TriggerConditionRule(compare_variable, validate_compare,
                                                   version="5.0-r31f"))
    return rules.with_family("trigger_actions", actions).with_family(
        "trigger_conditions", conditions)


def has_logic_variables(data):
    """Scan native trigger + optional pages; legacy projects keep old manifests."""
    for mission in data.get("missions", ()):
        for trigger in mission.get("triggers", ()):
            if trigger.get("condition") == "logic_compare":
                return True
            if _has_compare(trigger.get("when")):
                return True
            actions = list(trigger.get("actions", ()))
            for page in trigger.get("pages", ()):
                if page.get("condition") == "logic_compare" or _has_compare(page.get("when")):
                    return True
                actions.extend(page.get("actions", ()))
            if any(action.get("kind") in ("logic_set", "logic_add")
                   for action in actions):
                return True
    return False


def _has_compare(node):
    if type(node) is not dict:
        return False
    if node.get("condition") == "logic_compare":
        return True
    if "not" in node:
        return _has_compare(node["not"])
    return any(_has_compare(child) for op in ("all", "any")
               for child in node.get(op, ()))
