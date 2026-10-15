"""R2.D typed cross-reference navigation across canonical project documents.

Only explicit, typed links are indexed. Results are advisory: missing or opaque
links remain the responsibility of Content/GameProject validators and migration
logic. This index must never authorize deletion, renaming IDs or serialization.
"""
from __future__ import annotations

from dataclasses import dataclass

from drawtemp.studio.workspace_model import Resource, resources


@dataclass(frozen=True)
class ReferenceEdge:
    source: Resource
    target: Resource
    field: str
    path: str


TARGET_FIELDS = {
    "link": "objects",         # mission-local switch -> door
    "object_id": "objects",
    "actor_id": "actors",
    "unit_id": "actors",
    "unit": "actors",
    "scene": "scenes",
    "next_scene": "scenes",
    "mission": "maps",
    "mission_id": "maps",
    "start_mission": "maps",
    "campaign_id": "campaigns",
    "clip_id": "cinematics",
}


def reference_edges(snapshot):
    """Build directional, typed, deduplicated links with stable resource keys."""
    pair = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
    content, project = pair["content"], pair["project"]
    index = {resource.key: resource for resource in resources(pair)}
    emitted = set()
    edges = []

    def add(source, family, target_id, path, field):
        if not isinstance(target_id, str) or not target_id:
            return
        mission = source.mission_id if family in ("objects", "actors") else ""
        target = index.get((family, mission, target_id))
        if target is None or target.key == source.key:
            return
        identity = (source.key, target.key, path)
        if identity in emitted:
            return
        emitted.add(identity)
        edges.append(ReferenceEdge(source, target, field, path))

    def walk(source, data, path):
        if isinstance(data, dict):
            for field, value in data.items():
                location = path + "." + str(field)
                family = TARGET_FIELDS.get(field)
                if family and isinstance(value, str):
                    add(source, family, value, location, field)
                # Keep linked actor IDs in explicit actor lists, not arbitrary
                # strings or human-readable text/dialogue.
                elif field == "next_missions" and isinstance(value, list):
                    for idx, target in enumerate(value):
                        add(source, "maps", target, location + f"[{idx}]", field)
                elif field == "entry_scenes" and isinstance(value, dict):
                    for key, target in value.items():
                        add(source, "scenes", target, location + "." + key, field)
                walk(source, value, location)
        elif isinstance(data, (list, tuple)):
            for idx, child in enumerate(data):
                walk(source, child, path + f"[{idx}]")

    owner = index.get(("project", "", "project"))
    if owner:
        # Project-level links (story entry points), excluding owned resource
        # subtrees which will be attributed to each authored resource.
        story = project.get("story", {})
        walk(owner, {"entry_scenes": story.get("entry_scenes", {})},
             "GameProject.story")
    for row in content.get("missions", ()):
        mid = row["id"]
        mission = index.get(("maps", "", mid))
        if mission:
            walk(mission, {"next_missions": row.get("next_missions", [])},
                 f"Content.missions[{mid}]")
        for field, family in (("units", "actors"), ("objects", "objects"),
                              ("triggers", "events")):
            for node in row.get(field, ()):
                source = index.get((family, mid, node["id"]))
                if source:
                    walk(source, node, f"Content.missions[{mid}].{field}[{node['id']}]")
    for family, field in (("campaigns", "campaigns"),
                          ("cinematics", "cinematics")):
        for node in project.get(field, ()):
            source = index.get((family, "", node["id"]))
            if source:
                walk(source, node, f"GameProject.{field}[{node['id']}]")
    for node in project.get("story", {}).get("scenes", ()):
        source = index.get(("scenes", "", node["id"]))
        if source:
            walk(source, node, f"GameProject.story.scenes[{node['id']}]")
    return tuple(edges)


def connections(snapshot, selected, direction="incoming"):
    """Links to/from selected resources, excluding unrelated same-name IDs."""
    if direction not in ("incoming", "outgoing"):
        raise ValueError("Unknown reference direction")
    keys = {resource.key for resource in selected}
    return tuple(edge for edge in reference_edges(snapshot)
                 if (edge.target.key if direction == "incoming"
                     else edge.source.key) in keys)


def resource_search(snapshot, query="", *, families=(), mission_id="",
                    favorites=None, referenced_by=(), uses=()):
    """UI-neutral faceted search, preserving resource identity and scope."""
    rows = resources(snapshot)
    needle = query.casefold().strip()
    favorites = None if favorites is None else set(favorites)
    kinds = set(families)
    incoming_keys = ({edge.source.key for edge in connections(
        snapshot, referenced_by, "incoming")} if referenced_by else None)
    outgoing_keys = ({edge.target.key for edge in connections(
        snapshot, uses, "outgoing")} if uses else None)
    return tuple(r for r in rows
                 if (not kinds or r.family in kinds)
                 and (not mission_id or r.mission_id == mission_id
                      or (r.family == "maps" and r.resource_id == mission_id))
                 and (favorites is None or r.key in favorites)
                 and (incoming_keys is None or r.key in incoming_keys)
                 and (outgoing_keys is None or r.key in outgoing_keys)
                 and (not needle or needle in (
                     r.title + " " + r.resource_id + " " + r.mission_id).casefold()))
