"""R49.B2 read-only reference integrity audit for the canonical Studio pair.

This is advisory only. It reuses R2 resource IDs and the R2.D typed reference
field vocabulary; it cannot change or validate Content/GameProject itself.
Large/hostile graphs are bounded and reported as *incomplete*, never clean.
"""
from __future__ import annotations

from dataclasses import dataclass

from drawtemp.studio.resource_links import TARGET_FIELDS
from drawtemp.studio.workspace_model import Resource, resources


@dataclass(frozen=True)
class ReferenceProblem:
    source: Resource
    family: str
    target_id: str
    field: str
    path: str

    @property
    def summary(self) -> str:
        return (
            "Référence introuvable : " + self.family + "/" + self.target_id +
            " — " + self.source.title + " (" + self.field + ")"
        )


@dataclass(frozen=True)
class ReferenceAudit:
    problems: tuple[ReferenceProblem, ...]
    truncated: bool
    scanned_nodes: int

    @property
    def passed(self) -> bool:
        # An incomplete scan is never reported as valid.
        return not self.problems and not self.truncated


def reference_audit(snapshot, *, max_nodes=20000, max_problems=200):
    """Find missing *typed* references in canonical owned resource subtrees.

    Cross-mission lookups for actors/objects use the source mission. Other
    references use global identity. Unknown domain-specific fields remain the
    responsibility of canonical validation; this audit does not guess.
    """
    if type(max_nodes) is not int or max_nodes < 1 or max_nodes > 1_000_000:
        raise ValueError("max_nodes must be an integer in 1..1000000")
    if type(max_problems) is not int or max_problems < 1 or max_problems > 10000:
        raise ValueError("max_problems must be an integer in 1..10000")
    pair = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
    content, project = pair["content"], pair["project"]
    index = {item.key: item for item in resources(pair)}
    problems = []
    emitted = set()
    nodes = 0
    truncated = False

    def add(source, family, value, field, path):
        nonlocal truncated
        if not isinstance(value, str) or not value:
            return
        mission = source.mission_id if family in ("objects", "actors") else ""
        if (family, mission, value) in index:
            return
        key = (source.key, family, mission, value, path)
        if key in emitted:
            return
        emitted.add(key)
        if len(problems) == max_problems:
            truncated = True
            return
        problems.append(ReferenceProblem(source, family, value, field, path))

    def walk(source, node, path, depth=0):
        nonlocal nodes, truncated
        if truncated:
            return
        if nodes >= max_nodes or depth > 40:
            truncated = True
            return
        nodes += 1
        if isinstance(node, dict):
            for field, value in node.items():
                if truncated:
                    break
                segment = path + "." + str(field)
                family = TARGET_FIELDS.get(field)
                if family and isinstance(value, str):
                    add(source, family, value, str(field), segment)
                elif field == "next_missions" and isinstance(value, list):
                    for i, target in enumerate(value):
                        add(source, "maps", target, str(field), segment + f"[{i}]")
                elif field == "entry_scenes" and isinstance(value, dict):
                    for entry, target in value.items():
                        add(source, "scenes", target, str(field), segment + "." + str(entry))
                walk(source, value, segment, depth + 1)
        elif isinstance(node, (list, tuple)):
            for i, item in enumerate(node):
                walk(source, item, path + f"[{i}]", depth + 1)
                if truncated:
                    break

    owner = index.get(("project", "", "project"))
    if owner is not None:
        walk(owner, {"entry_scenes": project.get("story", {}).get("entry_scenes", {})},
             "GameProject.story")
    for mission in content.get("missions", ()):
        if truncated:
            break
        mid = mission["id"]
        source = index.get(("maps", "", mid))
        if source is not None:
            walk(source, {"next_missions": mission.get("next_missions", [])},
                 f"Content.missions[{mid}]")
        for field, family in (("units", "actors"), ("objects", "objects"),
                              ("triggers", "events")):
            if truncated:
                break
            for row in mission.get(field, ()):
                source = index.get((family, mid, row["id"]))
                if source is not None:
                    walk(source, row,
                         f"Content.missions[{mid}].{field}[{row['id']}]")
                if truncated:
                    break
    for family, field in (("campaigns", "campaigns"), ("cinematics", "cinematics")):
        if truncated:
            break
        for row in project.get(field, ()):
            source = index.get((family, "", row["id"]))
            if source is not None:
                walk(source, row, f"GameProject.{field}[{row['id']}]")
            if truncated:
                break
    if not truncated:
        for row in project.get("story", {}).get("scenes", ()):
            source = index.get(("scenes", "", row["id"]))
            if source is not None:
                walk(source, row, f"GameProject.story.scenes[{row['id']}]")
            if truncated:
                break
    return ReferenceAudit(tuple(problems), truncated, nodes)


def problems_for_selection(audit: ReferenceAudit, selected):
    """Filter by stable identity; title duplication never mixes missions."""
    keys = {resource.key for resource in selected}
    return tuple(problem for problem in audit.problems
                 if problem.source.key in keys)
