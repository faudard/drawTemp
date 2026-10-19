"""R37.A — deterministic AI decision context, versioned blackboard and utility preview.

Headless, opt-in SDK. This module does not replace sporebound.ai's CT selector,
mutate a Battle, or execute commands. Its integer scores and diagnostics can
be inspected by future R37 Studio tooling and replay adapters.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import re

SCHEMA_VERSION = 1
MAX_FACTS = 64
MAX_POLICIES = 64
MAX_TESTS = 16
MAX_SCORE = 2**31 - 1
_ID = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class AIDecisionError(ValueError):
    """An invalid contract or a bounded-evaluation failure."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise AIDecisionError(code, message)


def _object(value, keys, label):
    if type(value) is not dict or set(value) != keys:
        _fail("invalid_shape", label + " has missing or unsupported fields")


def _id(value, label):
    if type(value) is not str or _ID.fullmatch(value) is None:
        _fail("invalid_id", label + " must be lowercase ASCII (1..64 chars)")


def _integer(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        _fail("invalid_number", label + " must be an integer in " +
              str(low) + ".." + str(high))


def _scalar(value):
    if type(value) is str:
        if len(value) > 128:
            _fail("invalid_value", "AI string exceeds 128 characters")
    elif type(value) is int:
        _integer(value, "AI integer", -1000000, 1000000)
    elif type(value) is not bool:
        _fail("invalid_value", "AI values must be JSON booleans, integers or strings")
    return value


def _values(values, label):
    if type(values) is not dict or len(values) > MAX_FACTS:
        _fail("fact_budget", label + " must be a mapping with at most 64 values")
    for key, value in values.items():
        _id(key, label + " key")
        _scalar(value)
    return dict(sorted(values.items()))


def validate_context(context):
    """Return a detached, JSON-compatible decision input.

    A context is supplied by the owning runtime's fixed tick (CT or realtime).
    Time, randomness, world state and the currently active actor are *not*
    inferred here; this prevents a second mutable simulation.
    """
    _object(context, {"schema_version", "actor_id", "mode", "tick", "seed",
                      "facts"}, "AI Decision Context")
    if type(context["schema_version"]) is not int or context["schema_version"] != 1:
        _fail("unsupported_schema", "Only AI Decision Context schema v1 is supported")
    _id(context["actor_id"], "actor_id")
    if context["mode"] not in ("ct", "realtime"):
        _fail("invalid_mode", "mode must be ct or realtime")
    _integer(context["tick"], "tick", 0, 2**53 - 1)
    _integer(context["seed"], "seed", 0, 2**32 - 1)
    return {**context, "facts": _values(context["facts"], "facts")}


def new_blackboard(actor_id):
    """Create an explicit, versioned blackboard; no hidden shared state."""
    _id(actor_id, "actor_id")
    return {"schema_version": 1, "actor_id": actor_id,
            "updated_tick": 0, "values": {}}


def validate_blackboard(blackboard):
    """Fail closed on future/legacy-unknown schemas and malformed snapshots."""
    _object(blackboard, {"schema_version", "actor_id", "updated_tick",
                         "values"}, "AI Blackboard")
    if type(blackboard["schema_version"]) is not int or blackboard["schema_version"] != 1:
        _fail("unsupported_schema", "Only AI Blackboard schema v1 is supported")
    _id(blackboard["actor_id"], "actor_id")
    _integer(blackboard["updated_tick"], "updated_tick", 0, 2**53 - 1)
    return {**blackboard, "values": _values(blackboard["values"], "blackboard")}


def update_blackboard(blackboard, changes, *, tick):
    """Return a new snapshot. Reject temporal regression and partial updates."""
    old = validate_blackboard(blackboard)
    _integer(tick, "tick", 0, 2**53 - 1)
    if tick < old["updated_tick"]:
        _fail("time_regression", "A blackboard cannot be written in an earlier tick")
    if type(changes) is not dict or len(changes) > MAX_FACTS:
        _fail("fact_budget", "changes must be a mapping with at most 64 values")
    values = dict(old["values"])
    for name, value in changes.items():
        _id(name, "change name")
        values[name] = _scalar(value)
    values = _values(values, "blackboard")
    return {"schema_version": 1, "actor_id": old["actor_id"],
            "updated_tick": tick, "values": values}


def _reference(name):
    if type(name) is not str:
        _fail("invalid_reference", "Fact reference must be a string")
    if name.startswith("blackboard."):
        _id(name[len("blackboard."):], "blackboard reference")
    else:
        _id(name, "fact reference")


def _compile_policies(policies):
    if type(policies) is not list or not 1 <= len(policies) <= MAX_POLICIES:
        _fail("policy_budget", "AI requires 1..64 candidate policies")
    seen = set()
    compiled = []
    for item in policies:
        _object(item, {"id", "action", "base", "when", "terms"}, "AI policy")
        _id(item["id"], "policy id")
        _id(item["action"], "action")
        if item["id"] in seen:
            _fail("duplicate_policy", "Repeated policy id: " + item["id"])
        seen.add(item["id"])
        _integer(item["base"], "base", -1000000, 1000000)
        when, terms = item["when"], item["terms"]
        if type(when) is not dict or len(when) > MAX_TESTS:
            _fail("policy_budget", "when exceeds 16 conditions")
        if type(terms) is not dict or len(terms) > MAX_TESTS:
            _fail("policy_budget", "terms exceeds 16 weighted facts")
        for name, expected in when.items():
            _reference(name)
            _scalar(expected)
        for name, weight in terms.items():
            _reference(name)
            _integer(weight, "weight", -1024, 1024)
        compiled.append(deepcopy(item))
    return sorted(compiled, key=lambda p: p["id"])


def _digest(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True).encode("utf-8")
    return sha256(canonical).hexdigest()


def evaluate_decision(context, blackboard, policies, *, fallback="wait"):
    """Evaluate a bounded, deterministic and explainable *proposal*.

    Policy shape: {id, action, base, when: {fact: exact_value},
                   terms: {fact: signed_integer_weight}}.
    Blackboard fields are addressed as blackboard.<name>. Conditions use
    exact JSON type equality (True never equals 1). Terms are fixed-point
    integers, never floating point. Missing/non-numeric terms exclude the
    policy rather than fabricating a default value. Ties use policy ID order.

    No game rules are bypassed: the game must validate/execute the proposed
    action through its own authoritative command pipeline.
    """
    context = validate_context(context)
    blackboard = validate_blackboard(blackboard)
    _id(fallback, "fallback")
    if context["actor_id"] != blackboard["actor_id"]:
        _fail("actor_mismatch", "A blackboard belongs to exactly one actor")
    if blackboard["updated_tick"] > context["tick"]:
        _fail("future_blackboard", "Blackboard state comes from a future tick")

    policy_list = _compile_policies(policies)
    facts = dict(context["facts"])
    facts.update({"blackboard." + k: v
                  for k, v in blackboard["values"].items()})
    traces = []
    eligible = []
    for policy in policy_list:
        reasons = []
        for key, expected in sorted(policy["when"].items()):
            actual = facts.get(key)
            if key not in facts or type(actual) is not type(expected) or actual != expected:
                reasons.append("condition:" + key)
        score = policy["base"]
        terms = []
        if not reasons:
            for key, weight in sorted(policy["terms"].items()):
                value = facts.get(key)
                if type(value) not in (int, bool):
                    reasons.append("missing_or_non_numeric:" + key)
                    continue
                contribution = int(value) * weight
                score += contribution
                terms.append({"fact": key, "value": int(value),
                              "weight": weight, "contribution": contribution})
            if abs(score) > MAX_SCORE:
                _fail("score_overflow", "Candidate score exceeds the 32-bit budget")
        valid = not reasons
        traces.append({"id": policy["id"], "action": policy["action"],
                       "eligible": valid, "score": score if valid else None,
                       "base": policy["base"], "terms": terms,
                       "reasons": reasons})
        if valid:
            eligible.append((score, policy["id"], policy["action"]))
    best = min(eligible, key=lambda row: (-row[0], row[1])) if eligible else None
    report = {"schema_version": SCHEMA_VERSION, "actor_id": context["actor_id"],
              "mode": context["mode"], "tick": context["tick"],
              "seed": context["seed"], "blackboard_tick": blackboard["updated_tick"],
              "action": best[2] if best else fallback,
              "policy_id": best[1] if best else None,
              "score": best[0] if best else None,
              "used_fallback": best is None, "candidates": traces}
    # Commit to *all* inputs, including ignored memory, not only the winner.
    # Replay tooling can detect a changed context/policy even if an action
    # happened to stay the same. Policies are normalized by stable ID first.
    report["inputs_digest"] = _digest({
        "context": context, "blackboard": blackboard,
        "policies": policy_list, "fallback": fallback})
    report["digest"] = _digest(report)
    return report


__all__ = ["SCHEMA_VERSION", "AIDecisionError", "validate_context",
           "new_blackboard", "validate_blackboard", "update_blackboard",
           "evaluate_decision"]
