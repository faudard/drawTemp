"""R38.3A — reviewable, typed identity refactoring of mission objects/actors.

Never use global string replacement: changes are rooted in one canonical
Content mission, with explicit R9/R31 and prefab provenance integration.
Unknown typed references in the target mission fail closed; textual dialogue,
asset paths, world metadata, and same-name entities elsewhere stay untouched.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

from drawtemp.sdk.authoring import AuthoringPlan, AuthoringSession
from drawtemp.sdk.logic_graph import compile_r9_triggers, NAMESPACE as LOGIC_NS
from sporebound.model import RuleError, require
from sporebound.prefab_variants import NAMESPACE as PREFAB_NS

MAX_CHANGES = 1024
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
SCOPED_FIELDS = {
    "objects": frozenset({"link", "object", "object_id"}),
    "actors": frozenset({"unit", "unit_id", "actor_id", "protected_id"}),
}


@dataclass(frozen=True)
class RefactorChange:
    path: str
    before: str
    after: str


@dataclass(frozen=True)
class RefactorReview:
    """Immutable impact list plus one revision-locked R1 transaction."""
    family: str
    mission_id: str
    old_id: str
    new_id: str
    changes: tuple[RefactorChange, ...]
    plan: AuthoringPlan

    @property
    def change_count(self):
        return len(self.changes)


def _validate_request(snapshot, family, mission_id, old_id, new_id):
    require(family in SCOPED_FIELDS, "Only mission-local actors/objects support R38.3A")
    for label, value in (("mission", mission_id), ("old", old_id), ("new", new_id)):
        require(type(value) is str and _ID.fullmatch(value) is not None,
                label + ": unsupported identity")
    require(old_id != new_id, "The new ID must differ")
    content = snapshot["content"]
    mission = next((row for row in content["missions"] if row["id"] == mission_id),
                   None)
    require(mission is not None, "Unknown mission")
    field = "objects" if family == "objects" else "units"
    ids = {row["id"] for row in mission[field]}
    require(old_id in ids, "Source resource is missing")
    require(new_id not in ids, "Destination ID already exists")
    # Prefab source member IDs remain unchanged; only placed-instance IDs move.
    return mission


def _apply_typed(content, project, family, mid, old_id, new_id):
    mission = next(row for row in content["missions"] if row["id"] == mid)
    changes: list[RefactorChange] = []
    typed = SCOPED_FIELDS[family]

    def write(container, key, path, *, before=None):
        value = container.get(key) if before is None else before
        if value != old_id:
            return
        require(type(value) is str, "Expected typed string at " + path)
        container[key] = new_id
        changes.append(RefactorChange(path, old_id, new_id))
        require(len(changes) <= MAX_CHANGES, "Refactor change budget exceeded")

    def replace_known(container, path, *, keys=typed):
        """Walk typed field/value pairs but never rewrite arbitrary strings."""
        if type(container) is dict:
            for key, value in container.items():
                target_path = path + "." + str(key)
                if key in keys and type(value) is str:
                    write(container, key, target_path)
                elif type(value) in (dict, list):
                    replace_known(value, target_path, keys=keys)
        elif type(container) is list:
            for i, value in enumerate(container):
                replace_known(value, path + "[" + str(i) + "]", keys=keys)

    # All mission-local IDs are qualified by mission, never searched globally.
    kind = "objects" if family == "objects" else "units"
    owned = next(row for row in mission[kind] if row["id"] == old_id)
    write(owned, "id", "Content.missions[id=" + mid + "]." + kind +
          "[id=" + old_id + "].id", before=old_id)

    prefix = "Content.missions[id=" + mid + "]"
    if family == "actors":
        write(mission, "protected_id", prefix + ".protected_id")
        levels = mission.get("unit_levels", {})
        if old_id in levels:
            require(new_id not in levels, "Duplicate unit floor identity")
            levels[new_id] = levels.pop(old_id)
            changes.append(RefactorChange(prefix + ".unit_levels[" + old_id + "]",
                                          old_id, new_id))
        for index, unit in enumerate(mission["units"]):
            tags = list(unit.get("tags", ()))
            for tag_index, tag in enumerate(tags):
                if tag == "formation:escort:" + old_id:
                    tags[tag_index] = "formation:escort:" + new_id
                    changes.append(RefactorChange(
                        prefix + ".units[" + str(index) + "].tags[" +
                        str(tag_index) + "]", tag, "formation:escort:" + new_id))
            if tags != list(unit.get("tags", ())):
                unit["tags"] = tags

    for index, group in enumerate(mission.get("editor_groups", ())):
        member_field = "object_ids" if family == "objects" else "unit_ids"
        for i, identity in enumerate(group[member_field]):
            if identity == old_id:
                group[member_field][i] = new_id
                changes.append(RefactorChange(
                    prefix + ".editor_groups[" + str(index) + "]." +
                    member_field + "[" + str(i) + "]", old_id, new_id))

    # R31 generated R9 triggers are immutable outputs. Prove their current
    # Content rows still match the graph before re-compiling with the new ID.
    generated = set()
    spec = project.get("extensions", {}).get(LOGIC_NS)
    if spec:
        for graph in spec["data"]["graphs"]:
            if graph["mission_id"] != mid:
                continue
            original = compile_r9_triggers(graph)
            ids = {row["id"] for row in original}
            rows = {row["id"]: row for row in mission["triggers"]}
            if any(rows.get(row["id"]) != row for row in original):
                # Only block graphs that *use* the renamed identity, not
                # unrelated graphs with already-divergent native triggers.
                probe = {"nodes": [node["params"] for node in graph["nodes"]]}
                def uses(value):
                    if type(value) is dict:
                        return any((key in typed and v == old_id)
                                   or uses(v) for key, v in value.items())
                    return type(value) is list and any(uses(v) for v in value)
                require(not uses(probe),
                        "R31 graph/native R9 event divergence; resolve before rename")
                continue
            graph_path = ("GameProject.extensions." + LOGIC_NS +
                          ".data.graphs[id=" + graph["id"] + "]")
            prior = len(changes)
            for node in graph["nodes"]:
                replace_known(node["params"], graph_path + ".nodes[id=" +
                              node["id"] + "].params")
            if len(changes) == prior:
                continue
            updated = compile_r9_triggers(graph)
            require([row["id"] for row in original] ==
                    [row["id"] for row in updated], "R31 graph identity changed")
            # Atomically replace the originally generated trigger rows.
            positions = [i for i, row in enumerate(mission["triggers"])
                         if row["id"] in ids]
            require(len(positions) == len(original) and
                    positions == list(range(positions[0],
                                            positions[0] + len(positions))),
                    "R31 native event ordering diverged")
            replacements = {row["id"]: row for row in updated}
            for position in positions:
                row = mission["triggers"][position]
                mission["triggers"][position] = replacements[row["id"]]
                changes.append(RefactorChange(
                    prefix + ".triggers[id=" + row["id"] + "]",
                    old_id, new_id))
            generated.update(ids)

    # R9 native triggers own their typed payloads; generated triggers cannot
    # be patched independently of their R31 graph definitions.
    for event in mission["triggers"]:
        if event["id"] in generated:
            continue
        replace_known(event, prefix + ".triggers[id=" + event["id"] + "]")

    # Mission-local object links (switch -> door, ram -> door, etc.).
    if family == "objects":
        for item in mission["objects"]:
            write(item, "link", prefix + ".objects[id=" + item["id"] + "].link")

    # R38.2 placed instances store canonical target IDs, never source IDs.
    instance_spec = project.get("extensions", {}).get(PREFAB_NS)
    if instance_spec:
        for instance in instance_spec["data"]["instances"]:
            if instance["mission_id"] != mid:
                continue
            mapping = instance["mapping"][kind]
            for source_id, target_id in mapping.items():
                if target_id == old_id:
                    mapping[source_id] = new_id
                    changes.append(RefactorChange(
                        "GameProject.extensions." + PREFAB_NS +
                        ".data.instances[id=" + instance["id"] + "].mapping." +
                        kind + "." + source_id, old_id, new_id))

    # Fail closed on any typed target field missed by the curated scopes.
    # This is deliberately limited to the target mission and corresponding
    # graph/instance records: IDs are allowed to coincide across missions.
    def audit(container, path):
        if type(container) is dict:
            for key, value in container.items():
                nxt = path + "." + str(key)
                if key in typed and value == old_id:
                    raise RuleError("Unsupported typed reference at " + nxt)
                if type(value) in (dict, list):
                    audit(value, nxt)
        elif type(container) is list:
            for i, value in enumerate(container):
                audit(value, path + "[" + str(i) + "]")
    audit(mission, prefix)
    if spec:
        for graph in spec["data"]["graphs"]:
            if graph["mission_id"] == mid:
                audit(graph["nodes"], "R31.graphs[id=" + graph["id"] + "].nodes")
    if instance_spec:
        for instance in instance_spec["data"]["instances"]:
            if instance["mission_id"] == mid:
                require(old_id not in instance["mapping"][kind].values(),
                        "Unmapped prefab instance reference")

    # Refuse opaque extension records that might own typed references to the
    # target mission. Their schema needs a dedicated, reviewed adapter first.
    for namespace, envelope in project.get("extensions", {}).items():
        if namespace in (LOGIC_NS, PREFAB_NS):
            continue
        def suspicious(value):
            if type(value) is dict:
                return any((k in typed and v == old_id) or suspicious(v)
                           for k, v in value.items())
            return type(value) is list and any(suspicious(v) for v in value)
        require(not suspicious(envelope.get("data", {})),
                "Unmigrated typed dependency in extension " + namespace)

    require(len(changes) <= MAX_CHANGES, "Refactor change budget exceeded")
    require(len({change.path for change in changes}) == len(changes),
            "Conflicting duplicate refactor paths")
    return tuple(changes)


def preview_rename_identity(session: AuthoringSession, family: str,
                            mission_id: str, old_id: str, new_id: str
                            ) -> RefactorReview:
    """Create a detached impact report and R1 preview; no live edits."""
    require(isinstance(session, AuthoringSession), "Expected R1 authoring session")
    snap = session.snapshot().to_dict()
    _validate_request(snap, family, mission_id, old_id, new_id)
    recorded = []

    def transform(content, project):
        recorded.extend(_apply_typed(content, project, family, mission_id, old_id, new_id))
        return content, project

    plan = session.preview_pair(
        transform, kind="r38.refactor.rename", mission_id=mission_id,
        views=("workspace", "inspector", "renderer", "minimap"))
    return RefactorReview(family, mission_id, old_id, new_id,
                          tuple(recorded), plan)


def apply_rename_identity(session: AuthoringSession, review: RefactorReview):
    """Apply exactly the previewed canonical pair with R1 revision protection."""
    require(isinstance(review, RefactorReview), "Expected R38 refactor review")
    return session.apply(review.plan)
