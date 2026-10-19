"""R43.B2 — structural formula editor for the existing version-1 Ability AST.

The expression is a strict TREE. There are no reference edges, arbitrary
scripts, string interpolation or eval. Node replacement is fail-closed,
bounded by the canonical R43.A 31-node/depth-5 validator.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.ability_contracts import (
    AbilityError, STATS, evaluate_formula, validate_ability,
)

DEFAULT_STATS = {"attack": 12, "magic": 12, "defense": 4, "resistance": 4}
CASES = (
    ("Faible", {"attack": 8, "magic": 6, "defense": 4, "resistance": 4}),
    ("Référence", DEFAULT_STATS),
    ("Élevé", {"attack": 30, "magic": 28, "defense": 15, "resistance": 15}),
)
OPERATORS = ("constant", "stat", "add", "subtract", "percent")
CHILD_KEYS = {"add": ("left", "right"),
              "subtract": ("left", "right"), "percent": ("input",),
              "constant": (), "stat": ()}


def _check_path(path):
    if type(path) not in (tuple, list) or len(path) > 5 or any(
            type(key) is not str or key not in ("left", "right", "input")
            for key in path):
        raise AbilityError("invalid_path", "Expected bounded structural node path")
    return tuple(path)


def node_at(formula, path):
    """Return detached node addressed by structural keys, never an alias."""
    p = _check_path(path)
    value = formula
    for key in p:
        if type(value) is not dict or key not in CHILD_KEYS.get(value.get("op"), ()):
            raise AbilityError("invalid_path", "Formula child does not exist")
        value = value[key]
    return deepcopy(value)


def describe_nodes(formula):
    """Indented tree rows, canonical traversal, selection paths stay stable."""
    evaluate_formula(formula, DEFAULT_STATS)
    output = []

    def walk(node, path):
        op = node["op"]
        if op == "constant":
            title = "Constante = " + str(node["value"])
        elif op == "stat":
            title = "Statistique : " + node["name"]
        elif op == "percent":
            title = "Pourcentage : " + str(node["amount"]) + "%"
        else:
            title = "Addition" if op == "add" else "Soustraction"
        output.append({"path": path, "depth": len(path),
                       "operator": op, "label": title})
        for key in CHILD_KEYS[op]:
            walk(node[key], (*path, key))

    walk(formula, ())
    return output


def replace_node(formula, path, *, op, value=0, name="attack", amount=100):
    """Copy-on-write AST retyping with fresh, explicit child defaults.

    A node change can never create a cycle because references are not stored.
    Existing child expressions survive when the operator already has the
    requested port. Unknown/mismatched paths and budget violations reject
    the whole update with no mutation of the original graph.
    """
    path = _check_path(path)
    if type(op) is not str or op not in OPERATORS:
        raise AbilityError("invalid_formula", "Unsupported graph operator")
    if type(value) is not int or not 0 <= value <= 10000:
        raise AbilityError("invalid_integer", "Constant must be in 0..10000")
    if type(name) is not str or name not in STATS:
        raise AbilityError("invalid_formula", "Unknown statistic")
    if type(amount) is not int or not 0 <= amount <= 400:
        raise AbilityError("invalid_integer", "Percentage must be in 0..400")
    current = node_at(formula, path)
    original = deepcopy(formula)
    fallback = lambda: {"op": "constant", "value": 0}
    if op == "constant":
        next_node = {"op": op, "value": value}
    elif op == "stat":
        next_node = {"op": op, "name": name}
    elif op == "percent":
        next_node = {"op": op, "input": deepcopy(current.get("input", fallback()))
                     if current["op"] == "percent" else deepcopy(current),
                     "amount": amount}
        # Replacing a stat/constant by percent wraps the current expression.
        # A repeated percent edit preserves the existing input exactly.
    else:
        next_node = {
            "op": op,
            "left": deepcopy(current["left"])
            if current["op"] in ("add", "subtract") else deepcopy(current),
            "right": deepcopy(current["right"])
            if current["op"] in ("add", "subtract") else fallback(),
        }

    if not path:
        result = next_node
    else:
        cursor = original
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = next_node
        result = original
    evaluate_formula(result, DEFAULT_STATS)
    return result


def balance_lab(ability, *, cases=CASES):
    """Preview-only, deterministic formula tables, no fake battle simulation.

    Damage/healing are raw power, not final HP deltas. No RNG, crit, target
    resistance, armor, hits, cooldown application or actual Player adapter.
    """
    authored = validate_ability(ability)
    if type(cases) not in (list, tuple) or not 1 <= len(cases) <= 12:
        raise AbilityError("invalid_cases", "Balance Lab needs 1..12 profiles")
    output = []
    for label, stats in cases:
        if type(label) is not str or not 1 <= len(label.strip()) <= 64:
            raise AbilityError("invalid_case", "Invalid profile label")
        powers = [
            evaluate_formula(effect["formula"], stats)
            for effect in authored["effects"]
        ]
        output.append({
            "label": label,
            "stats": deepcopy(stats),
            "effects": [
                {"index": index, "kind": effect["kind"], "scope": effect["scope"],
                 "power": powers[index], "duration": effect["duration"]}
                for index, effect in enumerate(authored["effects"])
            ],
            "raw_damage_sum": sum(
                powers[i] for i, effect in enumerate(authored["effects"])
                if effect["kind"] == "damage"),
            "raw_heal_sum": sum(
                powers[i] for i, effect in enumerate(authored["effects"])
                if effect["kind"] == "heal"),
        })
    return {
        "ability": authored["id"],
        "cases": output,
        "simulation": False,
        "note": ("Puissance brute de formule (sans multiplicité des cibles, "
                 "armure/résistance, précision, RNG, combos ni runtime Player)"),
    }


__all__ = [
    "DEFAULT_STATS", "CASES", "OPERATORS", "CHILD_KEYS", "node_at",
    "describe_nodes", "replace_node", "balance_lab",
]
