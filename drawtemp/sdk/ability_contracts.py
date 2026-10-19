"""R43.A — opt-in, versioned Ability/Effect contracts using canonical Content.

No eval/exec, Qt state, random draws or independent combat engine. Native CT
skills are compiled into Content in the SAME AuthoringSession transaction as
their GameProject authoring document. Other modes expose validated plans only;
their Player adapters must explicitly opt in in R43.B/C.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
import re

from sporebound.model import Effect, RuleError, Skill

NAMESPACE = "org.drawtemp.abilities"
VERSION = 1
MODES = frozenset(("TACTICAL_CT", "ACTION_REALTIME", "RPG_TURN"))
STATS = frozenset(("attack", "magic", "defense", "resistance"))
EFFECTS = frozenset(("damage", "heal", "status", "cleanse", "mp"))
SHAPES = frozenset(("single", "diamond", "cross", "square"))
TEAMS = frozenset(("enemy", "ally", "unit", "self", "ground", "downed"))
SCOPES = frozenset(("target", "allies", "enemies", "all"))
IDENTIFIER = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")


class AbilityError(RuleError):
    """Stable diagnostics, suitable for Studio error panels."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise AbilityError(code, message)


def _exact(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        _fail("invalid_shape", label + ": missing or unsupported fields")


def _int(value, lower, upper, label):
    if type(value) is not int or not lower <= value <= upper:
        _fail("invalid_integer", f"{label} must be an integer in {lower}..{upper}")


def _formula(formula, depth=0, budget=None):
    """Validate an integer expression tree with strict node/depth budgets."""
    if budget is None:
        budget = [0]
    budget[0] += 1
    if budget[0] > 31 or depth > 5:
        _fail("formula_budget", "Formula exceeds 31 nodes or depth 5")
    if type(formula) is not dict:
        _fail("invalid_formula", "Formula must be a typed object")
    op = formula.get("op")
    if op == "constant":
        _exact(formula, {"op", "value"}, "constant")
        _int(formula["value"], 0, 10000, "constant")
    elif op == "stat":
        _exact(formula, {"op", "name"}, "stat")
        if type(formula["name"]) is not str or formula["name"] not in STATS:
            _fail("invalid_formula", "Unknown stat")
    elif op in ("add", "subtract"):
        _exact(formula, {"op", "left", "right"}, op)
        _formula(formula["left"], depth + 1, budget)
        _formula(formula["right"], depth + 1, budget)
    elif op == "percent":
        _exact(formula, {"op", "input", "amount"}, "percent")
        _int(formula["amount"], 0, 400, "percentage")
        _formula(formula["input"], depth + 1, budget)
    else:
        _fail("invalid_formula", "Only constant/stat/add/subtract/percent are allowed")


def evaluate_formula(formula, stats):
    """Deterministic integer floor rounding; result saturates to 0..10000."""
    _formula(formula)
    _exact(stats, STATS, "stats")
    for name, value in stats.items():
        _int(value, 0, 10000, name)

    def compute(node):
        op = node["op"]
        if op == "constant":
            value = node["value"]
        elif op == "stat":
            value = stats[node["name"]]
        elif op == "add":
            value = compute(node["left"]) + compute(node["right"])
        elif op == "subtract":
            value = compute(node["left"]) - compute(node["right"])
        else:
            value = compute(node["input"]) * node["amount"] // 100
        return max(-1000000000, min(1000000000, value))

    return max(0, min(10000, compute(formula)))


def validate_ability(ability):
    """Validate a detached, strictly typed v1 authoring document."""
    _exact(ability, {"schema_version", "id", "name", "profiles", "cost",
                     "target", "timing", "effects"}, "ability")
    _int(ability["schema_version"], VERSION, VERSION, "ability schema")
    if type(ability["id"]) is not str or not IDENTIFIER.fullmatch(ability["id"]):
        _fail("invalid_id", "Ability id must be lowercase ASCII (1..48)")
    if type(ability["name"]) is not str or not 1 <= len(ability["name"].strip()) <= 80:
        _fail("invalid_name", "Ability name must be 1..80 characters")
    profiles = ability["profiles"]
    if (type(profiles) is not list or not profiles or len(profiles) > 3 or
            any(type(mode) is not str or mode not in MODES for mode in profiles) or
            len(set(profiles)) != len(profiles)):
        _fail("unsupported_mode", "Use unique, supported combat profiles")
    _exact(ability["cost"], {"resource", "amount"}, "cost")
    resource = ability["cost"]["resource"]
    if type(resource) is not str or resource not in ("mp", "stamina"):
        _fail("unsupported_resource", "Only mp and stamina are available")
    _int(ability["cost"]["amount"], 0, 100, "cost")
    if "TACTICAL_CT" in profiles and resource != "mp":
        _fail("unsupported_resource", "Native CT skills consume mp")
    target = ability["target"]
    _exact(target, {"team", "shape", "min_range", "range", "radius"}, "target")
    if type(target["team"]) is not str or target["team"] not in TEAMS:
        _fail("invalid_target", "Unsupported team selector")
    if type(target["shape"]) is not str or target["shape"] not in SHAPES:
        _fail("invalid_target", "Unsupported area shape")
    for field, high in (("min_range", 16), ("range", 16), ("radius", 8)):
        _int(target[field], 0, high, field)
    if target["min_range"] > target["range"]:
        _fail("invalid_target", "Minimum range exceeds maximum")
    if target["shape"] == "single" and target["radius"] != 0:
        _fail("invalid_target", "Single-target ability needs radius 0")
    timing = ability["timing"]
    if type(timing) is not dict or set(timing) != set(profiles):
        _fail("invalid_timing", "One timing record per declared profile is required")
    for mode, row in timing.items():
        _exact(row, {"windup", "cooldown"}, "timing")
        _int(row["windup"], 0, 100, "windup")
        _int(row["cooldown"], 0, 10000, "cooldown")
        if mode == "TACTICAL_CT" and row["cooldown"]:
            _fail("unsupported_timing", "CT has no native cooldown storage")
    effects = ability["effects"]
    if type(effects) is not list or not 1 <= len(effects) <= 8:
        _fail("effect_budget", "An ability requires 1..8 ordered effects")
    from sporebound.rules import default_rules
    statuses = default_rules().statuses
    for effect in effects:
        _exact(effect, {"kind", "formula", "element", "status",
                        "duration", "scope"}, "effect")
        if type(effect["kind"]) is not str or effect["kind"] not in EFFECTS:
            _fail("unsupported_effect", "Effect is not in the native allowlist")
        if type(effect["element"]) is not str or effect["element"] not in (
                "physical", "fire", "ice", "lightning", "holy", "dark"):
            _fail("invalid_element", "Unknown element")
        if type(effect["scope"]) is not str or effect["scope"] not in SCOPES:
            _fail("invalid_scope", "Unknown target scope")
        _int(effect["duration"], 1, 10000, "effect duration")
        if effect["kind"] in ("status", "cleanse"):
            if type(effect["status"]) is not str or effect["status"] not in statuses:
                _fail("invalid_status", "Unknown native status")
        elif effect["status"] != "":
            _fail("invalid_status", "Only status/cleanse effects name a status")
        _formula(effect["formula"])
    return deepcopy(ability)


def validate_catalog(data):
    _exact(data, {"version", "abilities"}, "ability catalog")
    _int(data["version"], VERSION, VERSION, "catalog version")
    abilities = data["abilities"]
    if type(abilities) is not list or len(abilities) > 32:
        _fail("catalog_budget", "Catalog is limited to 32 abilities")
    result = [validate_ability(ability) for ability in abilities]
    ids = [ability["id"] for ability in result]
    if len(ids) != len(set(ids)):
        _fail("duplicate_ability", "Ability identifiers must be unique")
    return {"version": VERSION, "abilities": result}


def catalog_from_project(project):
    """Legacy projects have an empty, *in-memory* opt-in catalog."""
    if hasattr(project, "to_dict"):
        project = project.to_dict()
    if type(project) is not dict:
        _fail("invalid_project", "Expected canonical GameProject")
    extensions = project.get("extensions", {})
    if type(extensions) is not dict:
        _fail("invalid_project", "Project extensions must be an object")
    entry = extensions.get(NAMESPACE)
    if entry is None:
        return {"version": VERSION, "abilities": []}
    if (type(entry) is not dict or entry.get("schema_version") != 1 or
            set(entry) - {"schema_version", "data", "references"} or
            "data" not in entry or
            ("references" in entry and entry["references"] != [])):
        _fail("unsupported_schema", "Ability extension needs explicit migration")
    return validate_catalog(entry["data"])


def digest_ability(ability):
    authored = validate_ability(ability)
    payload = json.dumps(authored, sort_keys=True, ensure_ascii=True,
                         separators=(",", ":"), allow_nan=False)
    return sha256(payload.encode("utf-8")).hexdigest()


def resolve_ability(ability, *, mode, stats):
    """Return a replay-stable execution *plan*, not an invented new runtime."""
    authored = validate_ability(ability)
    if type(mode) is not str or mode not in authored["profiles"]:
        _fail("unsupported_mode", "Ability not enabled for this scene profile")
    rows = []
    for effect in authored["effects"]:
        rows.append({**deepcopy(effect),
                     "power": evaluate_formula(effect["formula"], stats)})
        rows[-1].pop("formula")
    return {"schema_version": VERSION, "id": authored["id"],
            "digest": digest_ability(authored), "mode": mode,
            "cost": deepcopy(authored["cost"]),
            "target": deepcopy(authored["target"]),
            "timing": deepcopy(authored["timing"][mode]), "effects": rows}


def compile_ct_skill(ability):
    """Lower the v1 CT-compatible subset to the existing native Skill schema.

    Dynamic formulas and non-native timing fail closed until an explicit
    Battle adapter is implemented; they never silently fall back to constants.
    """
    authored = validate_ability(ability)
    if "TACTICAL_CT" not in authored["profiles"]:
        _fail("unsupported_mode", "This ability does not opt in to tactical CT")
    effects = []
    for row in authored["effects"]:
        if row["formula"]["op"] != "constant":
            _fail("unsupported_formula", "Dynamic CT formulas need a native adapter")
        effects.append(Effect(kind=row["kind"], power=row["formula"]["value"],
                              element=row["element"], status=row["status"],
                              duration=row["duration"], scope=row["scope"]))
    t, target = authored["timing"]["TACTICAL_CT"], authored["target"]
    return asdict(Skill(
        id=authored["id"], name=authored["name"], effects=effects,
        cost=authored["cost"]["amount"], range=target["range"],
        min_range=target["min_range"], radius=target["radius"],
        shape="diamond" if target["shape"] == "single" else target["shape"],
        target=target["team"], cast_ticks=t["windup"]))


def preview_ability(session, ability):
    """Atomically preview a GameProject edit and optional native Content skill.

    Native hand edits are never clobbered. apply/undo/redo/save remain owned
    entirely by AuthoringSession, with its optimistic revision checks.
    """
    from drawtemp.sdk.authoring import AuthoringSession
    if not isinstance(session, AuthoringSession):
        _fail("invalid_session", "Expected canonical AuthoringSession")
    authored = validate_ability(ability)

    def transform(content, project):
        catalog = catalog_from_project(project)
        old = next((row for row in catalog["abilities"]
                    if row["id"] == authored["id"]), None)
        catalog["abilities"] = [row for row in catalog["abilities"]
                               if row["id"] != authored["id"]]
        catalog["abilities"].append(deepcopy(authored))
        validate_catalog(catalog)
        skills = content["skills"]
        matches = [index for index, row in enumerate(skills)
                   if row["id"] == authored["id"]]
        if len(matches) > 1:
            _fail("duplicate_native", "Duplicate native skill identity")
        if old and "TACTICAL_CT" in old["profiles"]:
            expected = compile_ct_skill(old)
            if not matches or skills[matches[0]] != expected:
                _fail("native_conflict", "Native CT skill was edited independently")
            skills.pop(matches[0])
        elif matches and "TACTICAL_CT" in authored["profiles"]:
            _fail("native_conflict", "A native skill already owns this ID")
        if "TACTICAL_CT" in authored["profiles"]:
            skills.append(compile_ct_skill(authored))
        project.setdefault("extensions", {})[NAMESPACE] = {
            "schema_version": 1, "data": catalog, "references": []}
        return content, project

    return session.preview_pair(transform, kind="r43-ability",
                                views=("workspace", "inspector"))


__all__ = ["NAMESPACE", "VERSION", "AbilityError", "validate_ability",
           "validate_catalog", "catalog_from_project", "digest_ability",
           "evaluate_formula", "resolve_ability", "compile_ct_skill",
           "preview_ability"]
