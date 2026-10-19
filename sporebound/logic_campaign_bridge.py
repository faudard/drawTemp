"""R31.G — explicit, fail-closed Battle -> Campaign.story_flags settlement bridge.

Bridge definitions live in GameProject.extensions and are gameplay-affecting
(covered by gameplay_project_digest). Only a finished authenticated Battle's
R31.F journal can supply values; there is no mutation during battle or on a
debug snapshot. Campaign itself is the sole persistent flag store.
"""
from __future__ import annotations

from copy import deepcopy

from .logic_variables import _VARIABLE, variables_from_journal
from .model import require

EXTENSION = "org.drawtemp.logic.campaign"
MAX_BINDINGS = 64
OUTCOMES = ("victory", "defeat", "both")


def _valid_name(name):
    return type(name) is str and _VARIABLE.fullmatch(name) is not None


def bridge_bindings(project):
    """Validate the shape even for direct in-memory GameProject consumers."""
    spec = project.extensions.get(EXTENSION)
    if spec is None:
        return []
    require(type(spec) is dict and
            set(spec) == {"schema_version", "data", "references"} and
            type(spec["schema_version"]) is int and spec["schema_version"] == 1,
            "Invalid R31.G bridge envelope")
    data = spec["data"]
    require(type(data) is dict and set(data) == {"bindings"} and
            type(data["bindings"]) is list and len(data["bindings"]) <= MAX_BINDINGS,
            "Invalid R31.G binding catalog")
    bindings = data["bindings"]
    refs = spec["references"]
    require(type(refs) is list and
            refs == [{"kind": "mission", "id": mission}
                     for mission in sorted({row["mission"] for row in bindings}
                                           if type(row) is dict and
                                           type(row.get("mission")) is str)],
            "R31.G references must match binding missions")
    used = set()
    for row in bindings:
        require(type(row) is dict and
                set(row) == {"mission", "source", "target", "result"} and
                type(row["mission"]) is str and _valid_name(row["source"]) and
                _valid_name(row["target"]) and row["result"] in OUTCOMES,
                "Invalid R31.G binding parameters")
        require(row["target"] not in used,
                "Each campaign flag must have one R31.G writer")
        used.add(row["target"])
    return deepcopy(bindings)


def validate_bridge(project, content):
    bindings = bridge_bindings(project)
    for row in bindings:
        require(row["mission"] in content.missions, "Unknown R31.G mission")
        mission = content.missions[row["mission"]]
        require(any(
            action.get("kind") in ("logic_set", "logic_add") and
            action.get("name") == row["source"]
            for trigger in mission.triggers
            for action in (
                list(trigger.get("actions", ())) +
                [action for page in trigger.get("pages", ())
                 for action in page.get("actions", ())])
        ), "R31.G source variable must be authored in its mission")
    return bindings


def apply_bridge(progress, project, battle):
    """Modify only a *detached* Campaign snapshot after settlement succeeds.

    Set is idempotent for an identical completed battle; retrying a finalized
    GameSession is already guarded by finalized/settled_fronts in the caller.
    Missing optional variables are skipped, never defaulted to zero/False.
    """
    require(battle.result in ("victory", "defeat"),
            "R31.G exports require a final tactical result")
    bindings = bridge_bindings(project)
    selected = [row for row in bindings
                if row["mission"] == battle.mission.id and
                row["result"] in (battle.result, "both")]
    if not selected:
        return progress
    values = variables_from_journal(battle)
    updated = deepcopy(progress)
    for row in selected:
        if row["source"] not in values:
            continue
        name, value = row["target"], deepcopy(values[row["source"]])
        old = updated.story_flags.get(name)
        require(name not in updated.story_flags or type(old) is type(value),
                "R31.G export cannot change the type of an existing flag")
        require(name in updated.story_flags or len(updated.story_flags) < 1000,
                "Campaign flag budget exhausted")
        updated.story_flags[name] = value
    return updated
