"""R44.B: World Atlas authoring on the R1 transactional GameProject owner.

All edits are detached proposals; a validated preview is committed once via
AuthoringSession. Routes remain canonical R25 SceneRouter references.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.model import RuleError, require
from sporebound.world_graph44 import EXTENSION, BIOMES, PROJECTIONS, OBJECT_KINDS


@dataclass(frozen=True)
class WorldAtlasPreview:
    plan: object
    report: dict


def _scene_catalog(snapshot):
    state = snapshot.to_dict()
    return state["content"], state["project"]


def default_world_atlas(session: AuthoringSession):
    """Propose a simple atlas for all R25-reachable scenes. Never apply it."""
    if not isinstance(session, AuthoringSession):
        raise TypeError("Expected the active AuthoringSession")
    content, project = _scene_catalog(session.snapshot())
    raw = project.get("scene_routes", {})
    require(raw and raw.get("version") == 1, "R44 requires authored R25 scene routes")
    start = raw["start"]
    neighbors = {}
    for link in raw["links"]:
        neighbors.setdefault(link["source"], set()).add(link["destination"])
    seen, pending = set(), [start]
    while pending:
        current = pending.pop()
        if current not in seen:
            seen.add(current)
            pending.extend(sorted(neighbors.get(current, set()) - seen, reverse=True))
    known = set(project.get("exploration", {})) | {
        mission["id"] for mission in content["missions"]}
    require(seen <= known and len(seen) <= 256,
            "R44: canonical routes refer to too many or unknown scenes")
    ordered = [start] + sorted(seen - {start})
    scenes = [{"id": scene, "origin": [8 + (i % 6) * 16, 8 + (i // 6) * 16]}
              for i, scene in enumerate(ordered)]
    portals = []
    for link in sorted(raw["links"], key=lambda item: item["id"]):
        if link["source"] not in seen or link["destination"] not in seen:
            continue
        portals.append({
            "route": link["id"], "source": default_portal_source(
                content, project, link["source"]), "travel_cost": 1})
    return {"version": 1, "regions": [{
        "id": "world", "title": "Monde", "biome": "fields",
        "projection": "top_down", "scenes": scenes, "palette": [],
    }], "portals": portals, "objects": []}


def default_portal_source(content, project, scene_id):
    """An existing, authored walkable position, without synthetic geometry."""
    stage = project.get("exploration", {}).get(scene_id)
    if stage is not None:
        return list(stage["start"])
    mission = next((m for m in content["missions"] if m["id"] == scene_id), None)
    require(mission is not None, "R44 portal uses an unknown scene")
    hero = next((unit for unit in mission["units"] if unit["team"] == "player"), None)
    require(hero is not None, "R44 tactical portal needs a known player spawn")
    return list(hero["pos"])


def _copy(document):
    require(type(document) is dict and document.get("version") == 1,
            "R44 editor requires WorldGraph schema v1")
    return deepcopy(document)


def set_region(document, region_id, *, title=None, biome=None, projection=None):
    draft = _copy(document)
    region = next((r for r in draft["regions"] if r["id"] == region_id), None)
    require(region is not None, "R44: unknown region")
    if title is not None:
        require(type(title) is str and 0 < len(title.strip()) <= 120,
                "R44: invalid region title")
        region["title"] = title.strip()
    if biome is not None:
        require(biome in BIOMES, "R44: unknown biome")
        region["biome"] = biome
    if projection is not None:
        require(projection in PROJECTIONS, "R44: unsupported projection")
        region["projection"] = projection
    return draft


def place_scene(document, scene_id, origin):
    draft = _copy(document)
    require(type(origin) is list and len(origin) == 2
            and all(type(v) is int and 0 <= v <= 100000 for v in origin),
            "R44: scene origin must be a valid integer point")
    for region in draft["regions"]:
        for scene in region["scenes"]:
            if scene["id"] == scene_id:
                scene["origin"] = list(origin)
                return draft
    raise RuleError("R44: unknown atlas scene")


def assign_scene(document, scene_id, region_id, *, title=None):
    """Move a scene into an existing/new region, pruning emptied regions."""
    draft = _copy(document)
    source = next((r for r in draft["regions"]
                   if any(s["id"] == scene_id for s in r["scenes"])), None)
    require(source is not None, "R44: unknown atlas scene")
    target = next((r for r in draft["regions"] if r["id"] == region_id), None)
    require(target is not None or (
        type(region_id) is str and region_id.isascii()
        and 1 <= len(region_id) <= 64
        and all(ch.isalnum() or ch in "_-" for ch in region_id)),
        "R44: invalid new region ID")
    if target is source:
        return draft
    scene = next(s for s in source["scenes"] if s["id"] == scene_id)
    source["scenes"].remove(scene)
    if target is None:
        target = {"id": region_id, "title": title or region_id,
                  "biome": source["biome"], "projection": source["projection"],
                  "scenes": [], "palette": list(source["palette"])}
        draft["regions"].append(target)
    target["scenes"].append(scene)
    draft["regions"] = [r for r in draft["regions"] if r["scenes"]]
    return draft


def edit_portal(document, route_id, *, source=None, travel_cost=None,
                enabled=True, default_source=None):
    draft = _copy(document)
    require(type(enabled) is bool, "R44: portal inclusion must be a boolean")
    existing = next((p for p in draft["portals"] if p["route"] == route_id), None)
    if not enabled:
        require(existing is not None, "R44: portal is already excluded")
        draft["portals"].remove(existing)
        return draft
    if existing is None:
        require(type(route_id) is str and route_id,
                "R44: missing canonical route ID")
        existing = {"route": route_id, "source": deepcopy(default_source),
                    "travel_cost": 1}
        draft["portals"].append(existing)
    if source is not None:
        existing["source"] = list(source)
    if travel_cost is not None:
        existing["travel_cost"] = travel_cost
    return draft


def edit_object(document, scene_id, object_id, kind, flag, *, delete=False):
    draft = _copy(document)
    obj = next((o for o in draft["objects"]
                if o["scene"] == scene_id and o["id"] == object_id), None)
    if delete:
        require(obj is not None, "R44: unknown persistent object")
        draft["objects"].remove(obj)
    else:
        require(kind in OBJECT_KINDS, "R44: unknown object kind")
        if obj is None:
            obj = {"id": object_id, "scene": scene_id, "kind": kind, "flag": flag}
            draft["objects"].append(obj)
        else:
            obj.update(kind=kind, flag=flag)
    return draft


def preview_world_atlas(session: AuthoringSession, document,
                        *, expected_revision=None):
    """One canonical project transaction. No save and no implicit migration."""
    if not isinstance(session, AuthoringSession):
        raise TypeError("Expected the active AuthoringSession")
    snapshot = session.snapshot()
    if expected_revision is not None and snapshot.revision != expected_revision:
        raise RuleError("R44: stale atlas editor revision")
    require(type(document) is dict, "R44: atlas document must be an object")
    data = deepcopy(document)

    def edit(project):
        project.setdefault("extensions", {})[EXTENSION] = {
            "schema_version": 1, "data": deepcopy(data)}
        return project

    plan = session.preview_project(edit, kind="r44.world-atlas")
    prior = snapshot.to_dict()["project"].get("extensions", {}).get(EXTENSION, {})
    changed = prior != {"schema_version": 1, "data": data}
    return WorldAtlasPreview(plan, {
        "source_revision": snapshot.revision, "changed": changed,
        "regions": len(data["regions"]),
        "scenes": sum(len(r["scenes"]) for r in data["regions"]),
        "portals": len(data["portals"]), "objects": len(data["objects"])})


def apply_world_atlas(session: AuthoringSession, preview: WorldAtlasPreview):
    require(isinstance(preview, WorldAtlasPreview),
            "R44: expected a validated WorldAtlas preview")
    return session.apply(preview.plan)


__all__ = ["WorldAtlasPreview", "default_world_atlas", "preview_world_atlas",
           "apply_world_atlas", "place_scene", "assign_scene", "set_region",
           "edit_portal", "edit_object", "default_portal_source"]
