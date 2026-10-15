"""R13.6: validated encounter authoring on the canonical Content model.

Temporary simulations do not change authored data. Persistent edits go only
through R1 AuthoringSession preview/apply/history/two-file saves.
"""
from __future__ import annotations

from copy import deepcopy

from sporebound.battle_lab import run_lab
from sporebound.model import Content, require

from .r13_combat_lab import compare_encounters

EDIT_FIELDS = frozenset({
    "unit_positions", "unit_overrides", "objective", "goal_cells",
    "protected_id", "target_ticks", "relic", "tile_changes",
})
EQUIPMENT_FIELDS = frozenset({
    "weapon", "attack_range", "min_range", "reaction", "support",
    "movement", "behavior", "skills", "tactics",
})
TERRAIN_FIELDS = frozenset({
    "height", "cost", "cover", "hazard", "blocked",
})


def _cell(raw, label):
    require(type(raw) in (list, tuple) and len(raw) == 2
            and all(type(v) is int for v in raw),
            label + " must be two integer coordinates")
    return tuple(raw)


def _edits(edits):
    require(type(edits) is dict and bool(edits) and set(edits) <= EDIT_FIELDS,
            "R13 encounter changes must be a non-empty supported edit object")
    return deepcopy(edits)


def build_encounter(content, mission_id, edits, *, rules=None):
    """Build a detached, validated tactical encounter.

    Content.validate remains the authority for objectives, terrain,
    formations, unit footprints, team composition, equipment and collisions.
    No fields bypass that validation and there are no implicit disk writes.
    """
    require(isinstance(content, Content) and mission_id in content.missions,
            "R13 authoring requires an existing mission")
    edits = _edits(edits)
    result = deepcopy(content)
    mission = result.missions[mission_id]
    units = {u.id: u for u in mission.units}

    positions = edits.get("unit_positions", {})
    require(type(positions) is dict and set(positions) <= set(units)
            and len(positions) <= 200, "Invalid unit placement edit")
    for uid, coords in positions.items():
        units[uid].pos = _cell(coords, "Unit position")

    overrides = edits.get("unit_overrides", {})
    require(type(overrides) is dict and set(overrides) <= set(units)
            and len(overrides) <= 200, "Invalid unit equipment edit")
    for uid, attributes in overrides.items():
        require(type(attributes) is dict and bool(attributes)
                and set(attributes) <= EQUIPMENT_FIELDS,
                "Unsupported unit equipment override")
        for key, value in attributes.items():
            if key in {"skills", "tactics"}:
                require(type(value) is list and len(value) <= 64
                        and all(type(v) is str for v in value),
                        "Skill and tactic edits require string lists")
            elif key in {"attack_range", "min_range"}:
                require(type(value) is int, "Range edit must be an integer")
            else:
                require(type(value) is str and bool(value),
                        "Invalid equipment or AI behavior")
            setattr(units[uid], key, deepcopy(value))

    if "objective" in edits:
        require(type(edits["objective"]) is str and bool(edits["objective"]),
                "Objective must be an authored ruleset id")
        mission.objective = edits["objective"]
    if "goal_cells" in edits:
        raw = edits["goal_cells"]
        require(type(raw) is list and len(raw) <= 512,
                "Goal cells must be a bounded list")
        cells = [_cell(item, "Goal cell") for item in raw]
        require(len(cells) == len(set(cells)), "Goal cells must be unique")
        mission.goal = cells
    if "protected_id" in edits:
        require(type(edits["protected_id"]) is str,
                "Protected actor id must be a string")
        mission.protected_id = edits["protected_id"]
    if "target_ticks" in edits:
        require(type(edits["target_ticks"]) is int,
                "Objective target ticks must be an integer")
        mission.target_ticks = edits["target_ticks"]
    if "relic" in edits:
        mission.relic = (None if edits["relic"] is None
                         else _cell(edits["relic"], "Relic location"))

    tiles = edits.get("tile_changes", [])
    require(type(tiles) is list and len(tiles) <= 128,
            "Terrain changes require at most 128 edited cells")
    seen = set()
    for entry in tiles:
        require(type(entry) is dict and
                set(entry) <= {"pos", *TERRAIN_FIELDS} and
                "pos" in entry and len(entry) >= 2,
                "Invalid terrain cell edit")
        pos = _cell(entry["pos"], "Terrain position")
        require(pos not in seen and mission.board.contains(pos),
                "Duplicate or out-of-bounds terrain edit")
        seen.add(pos)
        tile = deepcopy(mission.board.tile(pos))
        for key, value in entry.items():
            if key == "pos":
                continue
            require((type(value) is bool if key == "blocked"
                     else type(value) is int), "Invalid terrain value")
            setattr(tile, key, value)
        mission.board.tiles[pos] = tile
    result.validate(rules=rules)
    return result


def compare_draft(content, mission_id, edits, *, seeds=(1, 7, 42, 99),
                  max_commands=500, rules=None):
    """Simulate original and candidate with identical seeds and canonical AI.

    Objective changes are reported as an authored design difference, not as a
    claim that two different victory conditions are equivalent.
    """
    variant = build_encounter(content, mission_id, edits, rules=rules)
    baseline = run_lab(content, mission_id, seeds=seeds,
                       max_commands=max_commands, rules=rules)
    candidate = run_lab(variant, mission_id, seeds=seeds,
                        max_commands=max_commands, rules=rules)
    comparison = compare_encounters(baseline, candidate)
    original_mission = content.missions[mission_id]
    revised_mission = variant.missions[mission_id]
    objective_changed = (
        original_mission.objective != revised_mission.objective
        or original_mission.goal != revised_mission.goal
        or original_mission.target_ticks != revised_mission.target_ticks
        or original_mission.protected_id != revised_mission.protected_id
        or original_mission.relic != revised_mission.relic
    )
    # A different victory condition is meaningful evidence but NOT a passed
    # balance regression against a common objective.
    if objective_changed:
        comparison["passed"] = False
        comparison["issues"] = sorted(set([
            *comparison["issues"],
            "Objective changed: human design review / new baseline required",
        ]))
        comparison["human_signoff_required"] = True
    return {
        "schema": 1, "kind": "r13_encounter_draft",
        "mission": mission_id, "edits": deepcopy(edits),
        "baseline": baseline, "candidate": candidate,
        "comparison": comparison,
        "objective_changed": objective_changed,
        "replays_verified": all(s["replay_verified"]
                                for report in (baseline, candidate)
                                for s in report["samples"]),
    }


def preview_authoring(session, mission_id, edits):
    """Prepare an undoable R1 two-document transaction without applying it.

    The returned AuthoringPlan is tied to this session/revision. Only a
    separate, explicit session.apply(plan) commits; save remains opt-in.
    """
    from .authoring import AuthoringSession

    require(isinstance(session, AuthoringSession),
            "R13 commit requires an R1 AuthoringSession")
    edits = _edits(edits)

    def transform(data, project):
        source = Content.from_dict(data)
        candidate = build_encounter(source, mission_id, edits)
        return candidate.to_dict(), project

    return session.preview_pair(
        transform, kind="r13-encounter",
        mission_id=mission_id,
        views=("renderer", "minimap", "inspector", "workspace"),
    )
