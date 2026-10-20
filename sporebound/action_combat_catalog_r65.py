"""R65.B typed GameProject catalog; no separate action engine or executable graph.

The optional org.drawtemp.actioncombat extension stores authored R65.A rules
plus presentation-only timing cues and phase patterns. The latter are NOT boss
runtime logic until R65.C explicitly consumes them.
"""
from __future__ import annotations

from copy import deepcopy

from sporebound.action_combat_r65 import ActionCombatR65, validate_combat_rules
from sporebound.action_runtime import ActionError, _check, _id

NAMESPACE = "org.drawtemp.actioncombat"
CATALOG_VERSION = 1
_MAX_PRESETS = 12


def starter_preset(identifier="starter"):
    _check(_id(identifier), "Invalid combat preset ID")
    return {
        "id": identifier, "label": "Combat action",
        "rules": {
            "version": 1,
            "combo": [
                {"windup": 4, "active": 3, "recovery": 8, "range": 1200,
                 "damage": 2, "stagger": 6, "burn_ticks": 0},
            ],
            "projectile": {"speed": 600, "ttl": 15, "cooldown": 18,
                           "damage": 1, "stagger": 4, "burn_ticks": 0},
        },
        "telegraphs": [{"cue": "Attaque", "kind": "melee",
                        "stage": 0, "lead_ticks": 4}],
        "boss_patterns": [],
    }


def validate_preset(value):
    _check(type(value) is dict and set(value) == {
        "id", "label", "rules", "telegraphs", "boss_patterns"
    }, "Invalid R65 combat preset fields")
    _check(_id(value["id"]) and type(value["label"]) is str and
           1 <= len(value["label"].strip()) <= 80,
           "Invalid R65 preset identity")
    rules = validate_combat_rules(value["rules"])
    cues = value["telegraphs"]
    _check(type(cues) is list and len(cues) <= 24,
           "Invalid R65 telegraph catalogue")
    for cue in cues:
        _check(type(cue) is dict and set(cue) == {
            "cue", "kind", "stage", "lead_ticks"
        }, "Invalid R65 telegraph fields")
        _check(type(cue["cue"]) is str and 1 <= len(cue["cue"].strip()) <= 100
               and type(cue["kind"]) is str and
               cue["kind"] in ("melee", "projectile", "parry") and
               type(cue["stage"]) is int and
               ((cue["kind"] == "melee" and 0 <= cue["stage"] < len(rules["combo"]))
                or (cue["kind"] != "melee" and cue["stage"] == -1)) and
               type(cue["lead_ticks"]) is int and
               0 <= cue["lead_ticks"] <= 120,
               "Invalid R65 telegraph cue")
    patterns = value["boss_patterns"]
    _check(type(patterns) is list and len(patterns) <= 8,
           "Invalid R65 boss pattern catalogue")
    seen = set()
    for pattern in patterns:
        _check(type(pattern) is dict and set(pattern) == {
            "id", "phase", "hp_at_or_below", "steps"
        }, "Invalid boss pattern fields")
        _check(_id(pattern["id"]) and pattern["id"] not in seen and
               type(pattern["phase"]) is int and pattern["phase"] in (1, 2) and
               type(pattern["hp_at_or_below"]) is int and
               1 <= pattern["hp_at_or_below"] <= 100,
               "Invalid boss phase or duplicate ID")
        seen.add(pattern["id"])
        steps = pattern["steps"]
        _check(type(steps) is list and 1 <= len(steps) <= 16,
               "Invalid R65 boss step count")
        for step in steps:
            _check(type(step) is dict and set(step) == {
                "kind", "repeat", "wait_ticks"
            } and type(step["kind"]) is str and
                   step["kind"] in ("melee", "projectile", "dodge") and
                   type(step["repeat"]) is int and 1 <= step["repeat"] <= 8 and
                   type(step["wait_ticks"]) is int and 0 <= step["wait_ticks"] <= 180,
                   "Invalid R65 boss choreography step")
    return deepcopy(value)


def validate_catalog(catalog):
    _check(type(catalog) is dict and set(catalog) == {
        "version", "default", "presets"
    } and type(catalog["version"]) is int and
           catalog["version"] == CATALOG_VERSION,
           "Unsupported R65 catalog version")
    presets = catalog["presets"]
    _check(type(presets) is list and len(presets) <= _MAX_PRESETS,
           "Invalid R65 preset count")
    normalized = [validate_preset(p) for p in presets]
    identifiers = [row["id"] for row in normalized]
    _check(len(set(identifiers)) == len(identifiers),
           "Duplicate R65 preset ID")
    _check(type(catalog["default"]) is str and
           ((not identifiers and catalog["default"] == "") or
            (bool(identifiers) and catalog["default"] in identifiers)),
           "Invalid R65 default preset")
    return {"version": CATALOG_VERSION, "default": catalog["default"],
            "presets": normalized}


def catalog_from_project(project):
    """Read only an explicitly authored namespace, legacy projects remain inert."""
    if hasattr(project, "to_dict"):
        project = project.to_dict()
    _check(type(project) is dict and type(project.get("extensions", {})) is dict,
           "Invalid GameProject R65 extension owner")
    extension = project.get("extensions", {}).get(NAMESPACE)
    if extension is None:
        return {"version": 1, "default": "", "presets": []}
    _check(type(extension) is dict and
           set(extension) in ({"schema_version", "data"},
                              {"schema_version", "data", "references"}) and
           type(extension["schema_version"]) is int and
           extension["schema_version"] == 1 and
           extension.get("references", []) == [],
           "Invalid R65 extension envelope")
    return validate_catalog(extension["data"])


def preset_from_project(project, preset_id=None):
    catalog = catalog_from_project(project)
    if preset_id is None:
        preset_id = catalog["default"]
    _check(_id(preset_id), "Select an authored R65 preset")
    for preset in catalog["presets"]:
        if preset["id"] == preset_id:
            return deepcopy(preset)
    raise ActionError("Unknown authored R65 preset")


def runtime_from_project(scene, project, *, preset_id=None,
                         initial_inventory=None):
    """Explicit headless consumption; does not silently enable R65 in Player."""
    preset = preset_from_project(project, preset_id)
    return ActionCombatR65(scene, preset["rules"],
                           initial_inventory=initial_inventory)


def windows_preview(preset):
    """Bounded authoring timeline; never claims animations have been rendered."""
    spec = validate_preset(preset)
    tick = 0
    windows = []
    for index, move in enumerate(spec["rules"]["combo"]):
        for kind, duration in (("windup", move["windup"]),
                               ("active", move["active"]),
                               ("recovery", move["recovery"])):
            windows.append({"stage": index, "kind": kind,
                            "start_tick": tick, "end_tick": tick + duration})
            tick += duration
    return {"windows": windows, "total_ticks": tick,
            "telegraphs": deepcopy(spec["telegraphs"]),
            "boss_patterns": deepcopy(spec["boss_patterns"]),
            "note": "Fenêtres auteur, non synchronisées à une animation R36."}


def hitbox_preview(scene, preset, *, stage=0, facing=(1, 0)):
    """Exact R65 melee geometry at tile centers; no movement, AI, or damage.

    A 9x9 window around the hero is schematic, but its inclusion and LOS tests
    reuse the integer formulas and wall/door collision helpers from R65.A.
    """
    spec = validate_preset(preset)
    _check(type(stage) is int and 0 <= stage < len(spec["rules"]["combo"]),
           "Invalid preview stage")
    _check(type(facing) in (tuple, list) and len(facing) == 2 and
           all(type(v) is int and v in (-1, 0, 1) for v in facing) and
           any(facing), "Invalid preview facing")
    runtime = ActionCombatR65(scene, spec["rules"])
    move = spec["rules"]["combo"][stage]
    hx, hy = runtime.hero["pos"]
    fx, fy = facing
    cells = []
    blocked = []
    cx, cy = hx // 1000, hy // 1000
    for y in range(max(0, cy - 4), min(scene["height"], cy + 5)):
        for x in range(max(0, cx - 4), min(scene["width"], cx + 5)):
            point = [x * 1000 + 500, y * 1000 + 500]
            if runtime._solid_at(*point):
                blocked.append([x, y])
                continue
            dx, dy = point[0] - hx, point[1] - hy
            if (dx * dx + dy * dy <= move["range"] ** 2 and
                    dx * fx + dy * fy > 0 and
                    abs(dx * fy - dy * fx) <= 450 * max(1, abs(fx) + abs(fy)) and
                    runtime._ray_clear([hx, hy], point)):
                cells.append([x, y])
    return {"origin": [cx, cy], "facing": list(facing), "stage": stage,
            "cells": cells, "blocked": blocked,
            "note": "Hitbox R65 à centres de cases; aucune animation ni cible simulée."}
