"""3.8.2 Balance Matrix: paired multi-mission A/B scenarios on canonical Battle Lab.

Every scenario uses a deep-copied Content, actual AI/Battle and the *same*
ordered seeds. Encounter edits never leak into the Studio authoring document.
This is exploratory comparison, not a causal test or statistical confidence
interval. Independent CI gate compares matching scenarios between revisions.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json

from .battle_lab import compare_reports, run_lab
from .model import Content, require


SCHEMA = 1
MAX_CASES = 24
MAX_SEEDS = 64
# Additive, bounded knobs only. For HP preserve current injury proportion by
# applying the same absolute delta to max_hp and hp, clamped at 1..max_hp.
DELTA_STATS = {"max_hp", "max_mp", "attack", "magic", "defense",
               "magic_defense", "speed", "move", "weapon_power"}
EQUIPMENT_FIELDS = {"weapon", "attack_range", "min_range", "reaction",
                    "support", "movement", "behavior", "skills", "tactics"}
FIELDS = {"id", "mission", "remove_units", "team_deltas",
          "unit_deltas", "unit_overrides", "ruleset",
          "unit_positions", "clone_units", "inventory"}


def _check_deltas(value, label):
    require(type(value) is dict and bool(value)
            and set(value) <= DELTA_STATS
            and all(type(n) is int and -100 <= n <= 100 for n in value.values()),
            "Invalid " + label + " (integer stat deltas within ±100)")
    return dict(sorted(value.items()))


def _spec(raw, content, rulesets):
    require(type(raw) is dict and set(raw) <= FIELDS
            and type(raw.get("id")) is str
            and 1 <= len(raw["id"]) <= 64
            and type(raw.get("mission")) is str
            and raw["mission"] in content.missions,
            "Invalid matrix case id, mission or fields")
    require(raw["id"] != raw["mission"] + "::baseline",
            "The mission baseline id is reserved")
    require(type(raw.get("ruleset", "authored")) is str
            and raw.get("ruleset", "authored") in rulesets,
            "Unknown matrix ruleset")
    mission = content.missions[raw["mission"]]
    units = {u.id: u for u in mission.units}
    removed = raw.get("remove_units", [])
    require(type(removed) is list and len(removed) == len(set(removed))
            and all(type(uid) is str and uid in units for uid in removed),
            "Invalid or unknown units to remove")
    team_deltas = raw.get("team_deltas", {})
    unit_deltas = raw.get("unit_deltas", {})
    overrides = raw.get("unit_overrides", {})
    require(type(team_deltas) is dict and set(team_deltas) <= {"player", "enemy"}
            and type(unit_deltas) is dict and set(unit_deltas) <= units.keys()
            and type(overrides) is dict and set(overrides) <= units.keys()
            and not (set(removed) & (set(unit_deltas) | set(overrides))),
            "Invalid team/unit adjustment targets")
    for team, changes in team_deltas.items():
        _check_deltas(changes, team)
    for uid, changes in unit_deltas.items():
        _check_deltas(changes, uid)
    for uid, changes in overrides.items():
        require(type(changes) is dict and bool(changes)
                and set(changes) <= EQUIPMENT_FIELDS,
                "Unsupported tactical equipment override")
        # Canonical Content.validate performs range, enum and skill checks.
        for field, value in changes.items():
            if field in {"skills", "tactics"}:
                require(type(value) is list and all(type(s) is str for s in value),
                        "Invalid list override " + field)
            elif field in {"attack_range", "min_range"}:
                require(type(value) is int, "Invalid attack range override")
            else:
                require(type(value) is str, "Invalid equipment override")
    # R6 tuning: only alter cloned authored content. Content.validate checks
    # blocked tiles, footprints, heights, unit ids and actual rule constraints.
    positions = raw.get("unit_positions", {})
    require(type(positions) is dict and set(positions) <= set(units)
            and not set(positions).intersection(removed)
            and all(type(pos) in (tuple, list) and len(pos) == 2
                    and all(type(c) is int for c in pos)
                    for pos in positions.values()),
            "Invalid unit placement changes")
    clones = raw.get("clone_units", [])
    require(type(clones) is list and len(clones) <= 10
            and all(type(row) is dict
                    and set(row) == {"id", "template_id", "pos"}
                    and type(row["id"]) is str and 1 <= len(row["id"]) <= 64
                    and row["id"] not in units
                    and type(row["template_id"]) is str
                    and row["template_id"] in units
                    and row["template_id"] not in removed
                    and type(row["pos"]) in (tuple, list)
                    and len(row["pos"]) == 2
                    and all(type(c) is int for c in row["pos"])
                    for row in clones)
            and len({row["id"] for row in clones}) == len(clones),
            "Invalid cloned unit composition")
    inventory = raw.get("inventory")
    require(inventory is None or (
            type(inventory) is dict
            and set(inventory) == {"potion", "ether", "phoenix"}
            and all(type(n) is int and 0 <= n <= 1000
                    for n in inventory.values())),
            "Invalid initial inventory for player team")
    return {"id": raw["id"], "mission": raw["mission"],
            "unit_positions": deepcopy(positions),
            "clone_units": deepcopy(clones),
            "inventory": deepcopy(inventory),
            "remove_units": list(removed),
            "team_deltas": deepcopy(team_deltas),
            "unit_deltas": deepcopy(unit_deltas),
            "unit_overrides": deepcopy(overrides),
            "ruleset": raw.get("ruleset", "authored")}


def _apply_delta(unit, stat, value):
    old = getattr(unit, stat)
    new = old + value
    if stat == "max_hp":
        unit.max_hp = new
        unit.hp = max(1, min(new, unit.hp + value))
    elif stat == "max_mp":
        unit.max_mp = new
        unit.mp = max(0, min(new, unit.mp + value))
    else:
        setattr(unit, stat, new)


def scenario_content(content, spec, *, rules=None):
    """Create a validated isolated variant, retaining ordinary Content schema."""
    require(isinstance(content, Content), "Matrix expects Content")
    clone = deepcopy(content)
    mission = clone.missions[spec["mission"]]
    mission.units = [u for u in mission.units
                     if u.id not in spec["remove_units"]]
    for unit in mission.units:
        if unit.id in spec.get("unit_positions", {}):
            unit.pos = tuple(spec["unit_positions"][unit.id])
        for stat, delta in sorted(spec["team_deltas"].get(unit.team, {}).items()):
            _apply_delta(unit, stat, delta)
        for stat, delta in sorted(spec["unit_deltas"].get(unit.id, {}).items()):
            _apply_delta(unit, stat, delta)
        for key, value in sorted(spec["unit_overrides"].get(unit.id, {}).items()):
            setattr(unit, key, deepcopy(value))
    templates = {unit.id: unit for unit in content.missions[spec["mission"]].units}
    for entry in spec.get("clone_units", []):
        source = deepcopy(templates[entry["template_id"]])
        source.id = entry["id"]
        source.pos = tuple(entry["pos"])
        mission.units.append(source)
        if entry["template_id"] in mission.unit_levels:
            mission.unit_levels[entry["id"]] = mission.unit_levels[entry["template_id"]]
    clone.validate(rules=rules)
    return clone


def _row(case_id, mission, spec, report, baseline):
    ref = baseline
    pairs = [
        {"seed": new["seed"], "baseline": old["result"],
         "variant": new["result"],
         "ticks_delta": new["ticks"] - old["ticks"],
         "commands_delta": new["commands"] - old["commands"]}
        for old, new in zip(ref["samples"], report["samples"])
    ]
    require(all(a["seed"] == b["seed"] for a, b in
                zip(ref["samples"], report["samples"])),
            "Unpaired matrix seeds")
    return {
        "id": case_id, "mission": mission, "spec": spec,
        "reference": mission + "::baseline",
        "victory_delta": round(report["victory_rate"] -
                               ref["victory_rate"], 4),
        "ticks_p95_delta": report["ticks_p95"] - ref["ticks_p95"],
        "commands_p95_delta": report["commands_p95"] - ref["commands_p95"],
        "unresolved_delta": report["outcomes"]["limit"] -
                            ref["outcomes"]["limit"],
        "paired_seeds": pairs, "report": report,
    }


def run_matrix(content, cases, *, seeds=(1, 7, 42, 99),
               max_commands=500, rulesets=None):
    """Run 1..24 proposed cases plus one baseline per referenced mission.

    'rulesets' is an explicit mapping of user-supplied, already-authored RuleSet
    instances. This module never creates or guesses a custom gameplay ruleset.
    """
    require(isinstance(content, Content), "Matrix expects Content")
    require(type(cases) in (list, tuple) and 1 <= len(cases) <= MAX_CASES,
            "Provide 1..24 matrix cases")
    require(type(seeds) in (list, tuple) and 1 <= len(seeds) <= MAX_SEEDS
            and len(seeds) == len(set(seeds))
            and all(type(s) is int and 0 <= s < 2**32 for s in seeds),
            "Matrix seeds must be unique unsigned integers (1..64)")
    require(type(max_commands) is int and 1 <= max_commands <= 10000,
            "Matrix command cap must be 1..10000")
    rulesets = {"authored": None} if rulesets is None else rulesets
    require(type(rulesets) is dict and "authored" in rulesets
            and all(type(k) is str and bool(k) for k in rulesets),
            "Expected named rulesets with an authored baseline")
    specs = [_spec(case, content, rulesets) for case in cases]
    keys = [spec["id"] for spec in specs]
    require(len(keys) == len(set(keys)), "Duplicate matrix case id")
    missions = sorted(set(spec["mission"] for spec in specs))
    base = {}
    for mid in missions:
        base[mid] = run_lab(content, mid, seeds=seeds,
                            max_commands=max_commands,
                            rules=rulesets["authored"])
    rows = []
    for mid in missions:
        report = base[mid]
        rows.append(_row(mid + "::baseline", mid,
                         {"mission": mid, "ruleset": "authored"},
                         report, report))
    for spec in specs:
        rules = rulesets[spec["ruleset"]]
        variant = scenario_content(content, spec, rules=rules)
        setup = ({"inventory": spec["inventory"]}
                 if spec.get("inventory") is not None else None)
        report = run_lab(variant, spec["mission"], seeds=seeds,
                         max_commands=max_commands, rules=rules,
                         initial_state=setup)
        rows.append(_row(spec["id"], spec["mission"], spec, report,
                         base[spec["mission"]]))
    return {
        "kind": "balance_matrix", "schema": SCHEMA,
        "seeds": list(seeds), "max_commands": max_commands,
        "runs_per_case": len(seeds), "cases": rows,
        "case_count": len(rows),
        "mission_count": len(missions),
        "all_replays_verified": all(
            all(s["replay_verified"] for s in row["report"]["samples"])
            for row in rows),
    }


def compare_matrices(before, after, *, max_victory_drop=.25,
                     max_p95_growth=.30, max_new_limits=0):
    """Gate matching case ids across builds; never compare different missions."""
    for report in (before, after):
        require(type(report) is dict and report.get("kind") == "balance_matrix"
                and report.get("schema") == SCHEMA
                and type(report.get("cases")) is list
                and len(report["cases"]) == report.get("case_count")
                and type(report.get("seeds")) is list
                and report.get("case_count", 0) > 0, "Invalid matrix report")
    require(before["seeds"] == after["seeds"]
            and before["max_commands"] == after["max_commands"],
            "Matrix gate requires matching seeds and command cap")
    earlier = {row["id"]: row for row in before["cases"]}
    current = {row["id"]: row for row in after["cases"]}
    require(len(earlier) == len(before["cases"])
            and len(current) == len(after["cases"])
            and set(earlier) == set(current),
            "Matrix gate requires exactly matching case ids")
    rows, passed = [], True
    for key in sorted(earlier):
        first, last = earlier[key], current[key]
        require(first["mission"] == last["mission"],
                "Matrix case cannot switch missions across revisions")
        verdict = compare_reports(first["report"], last["report"],
                                  max_victory_drop=max_victory_drop,
                                  max_p95_growth=max_p95_growth,
                                  max_new_limits=max_new_limits)
        passed = passed and verdict["passed"]
        rows.append({"case": key, "mission": last["mission"],
                     "scenario_definition_changed": first["spec"] != last["spec"],
                     "comparison": verdict})
    return {"status": "pass" if passed else "fail", "passed": passed,
            "checked_cases": len(rows),
            "failures": [r["case"] for r in rows
                         if not r["comparison"]["passed"]],
            "comparisons": rows}


def save_matrix(path, matrix):
    from pathlib import Path
    require(type(matrix) is dict and matrix.get("kind") == "balance_matrix"
            and matrix.get("schema") == SCHEMA, "Not a Balance Matrix report")
    target = Path(path)
    target.write_text(json.dumps(matrix, sort_keys=True,
                                 indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    return target
