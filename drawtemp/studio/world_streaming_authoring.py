"""R54.B headless World Streaming Inspector and no-JSON authoring facade.

Only canonical GameProject.extensions and R25 scene_routes are authoritative.
Cell layouts, LOD suggestions and prefetch are deterministic *diagnostics*;
they do not run a second world simulation or mutate GameSession.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.model import RuleError, require
from sporebound.world_streaming import (
    EXTENSION, MAX_HISTORY, _id, validate_world_streaming,
)

DEFAULT_CACHE_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class StreamingPreview:
    plan: object
    report: dict


def _project(session):
    require(isinstance(session, AuthoringSession),
            "R54 Studio requires the canonical AuthoringSession")
    snap = session.snapshot().to_dict()
    return snap["project"], snap["revision"]


def manifest_from_routes(project, *, max_cache_bytes=DEFAULT_CACHE_BYTES):
    """Build a valid minimal R54 topology from bidirectional R25 portals.

    Only reciprocal exploration↔exploration edges are included. Inaccessible
    scenes are not silently registered as extra standalone worlds.
    """
    routes = project.get("scene_routes", {})
    scenes = project.get("exploration", {})
    require(type(routes) is dict and routes.get("version") == 1 and
            routes.get("start") in scenes and type(scenes) is dict,
            "Create canonical R25 exploration routes before R54 streaming")
    require(type(max_cache_bytes) is int and
            1024 <= max_cache_bytes <= 32 * 1024 * 1024,
            "Invalid R54 cache budget")
    links = routes.get("links", [])
    directed = {(row["source"], row["destination"]) for row in links
                if row["source"] in scenes and row["destination"] in scenes}
    adjacent = {scene: set() for scene in scenes}
    for source, dest in directed:
        if source != dest and (dest, source) in directed:
            adjacent[source].add(dest)
    start = routes["start"]
    reached, todo = {start}, deque([start])
    while todo:
        for neighbor in sorted(adjacent[todo.popleft()]):
            if neighbor not in reached:
                reached.add(neighbor)
                todo.append(neighbor)
    require(len(reached) <= 256 and all(_id(s) for s in reached),
            "R54 needs <=256 ASCII scene IDs (1..64 chars)")
    cells = [
        {"id": scene, "region": "world", "scene": scene,
         "neighbors": sorted(adjacent[scene] & reached), "entities": []}
        for scene in sorted(reached)]
    spec = {"version": 1, "start": start,
            "max_cache_bytes": max_cache_bytes, "cells": cells}
    validate_world_streaming(
        spec, SimpleNamespace(exploration=scenes, scene_routes=routes))
    return spec


def preview_streaming(session, document, *, expected_revision=None):
    """Stage a complete, undoable extension replacement with R1 validation."""
    project, revision = _project(session)
    require(expected_revision is None or revision == expected_revision,
            "Stale R54 Studio revision")
    require(document is None or type(document) is dict,
            "R54 document must be an object or None")
    proposed = deepcopy(document)
    before = project.get("extensions", {}).get(EXTENSION)

    def edit(current):
        extensions = current.setdefault("extensions", {})
        if proposed is None:
            extensions.pop(EXTENSION, None)
        else:
            extensions[EXTENSION] = {
                "schema_version": 1, "data": deepcopy(proposed),
                "references": []}
        return current

    plan = session.preview_project(edit, kind="r54.world-streaming.author")
    return StreamingPreview(plan, {
        "source_revision": revision, "before_enabled": before is not None,
        "after_enabled": proposed is not None,
        "cells": len(proposed["cells"]) if proposed is not None else 0,
        "budget_bytes": (proposed["max_cache_bytes"]
                         if proposed is not None else 0),
    })


def apply_streaming(session, preview):
    require(isinstance(session, AuthoringSession) and
            isinstance(preview, StreamingPreview),
            "Expected R54 Studio preview from active editor")
    return session.apply(preview.plan)


def prefetch_order(spec, focus, *, radius=1, limit=8):
    """Deterministic BFS, focus first. Strictly bounded by loader queue."""
    require(type(radius) is int and 0 <= radius <= 8 and
            type(limit) is int and 1 <= limit <= 8,
            "Invalid R54 prefetch depth or quota")
    require(type(spec) is dict and type(spec.get("cells")) is list,
            "Invalid R54 prefetch source")
    cells = {row["id"]: row for row in spec["cells"]}
    require(focus in cells, "Unknown R54 focus cell")
    queue, visited, result = deque([(focus, 0)]), {focus}, []
    while queue and len(result) < limit:
        current, distance = queue.popleft()
        result.append(current)
        if distance < radius:
            for neighbor in sorted(cells[current]["neighbors"]):
                require(neighbor in cells, "Unknown R54 neighbor")
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, distance + 1))
    return result


def inspect_streaming(document, project, *, focus=None, zoom=1.0,
                      cache_stats=None):
    """Presentation-only region graph, LOD hints and true cache statistics.

    'estimated_bytes' estimates 2D tile metadata, not resident GPU/asset RAM.
    Actual cache resident bytes come exclusively from WorldCellCache.stats().
    """
    require(type(zoom) in (float, int) and not isinstance(zoom, bool)
            and 0.25 <= zoom <= 4.0, "Zoom must be within 0.25..4")
    spec = validate_world_streaming(document, SimpleNamespace(
        exploration=project["exploration"],
        scene_routes=project["scene_routes"]))
    cells = {row["id"]: row for row in spec["cells"]}
    focus = spec["start"] if focus is None else focus
    require(focus in cells, "Unknown R54 focus cell")
    distances, queue = {focus: 0}, deque([focus])
    while queue:
        ident = queue.popleft()
        for neighbor in sorted(cells[ident]["neighbors"]):
            if neighbor not in distances:
                distances[neighbor] = distances[ident] + 1
                queue.append(neighbor)
    # Fixed, testable columns by BFS depth; deterministic order within column.
    columns = {}
    for ident in sorted(cells, key=lambda key: (distances[key], key)):
        depth = distances[ident]
        columns.setdefault(depth, []).append(ident)
    positions = {
        ident: [depth * 180 + 50, slot * 105 + 50]
        for depth, names in sorted(columns.items())
        for slot, ident in enumerate(names)}
    rows = []
    for ident in sorted(cells):
        cell = cells[ident]
        stage = project["exploration"][cell["scene"]]
        tiles = stage["width"] * stage["height"]
        # Tiny deterministic headless tile projection, never an image asset.
        blocked = {tuple(pos) for pos in stage.get("blocked", [])}
        preview_width = min(stage["width"], 8)
        preview_height = min(stage["height"], 4)
        tile_preview = [
            "".join("#" if (col, line) in blocked else "."
                    for col in range(preview_width))
            for line in range(preview_height)]
        distance = distances[ident]
        # Pure presentation tiers, no claim of renderer/GPU LOD selection.
        lod = ("detail" if zoom >= 1.0 and distance == 0 or
               zoom >= 2.0 and distance <= 1 else
               "overview" if zoom >= 0.5 and distance <= 1 else "outline")
        rows.append({
            "id": ident, "region": cell["region"], "scene": cell["scene"],
            "neighbors": list(cell["neighbors"]), "entities": len(cell["entities"]),
            "distance": distance, "lod": lod,
            "position": list(positions[ident]),
            "map_size": [stage["width"], stage["height"]],
            "tile_preview": tile_preview,
            "estimated_bytes": tiles * 16 + len(stage.get("blocked", [])) * 16,
        })
    links = sorted([{"from": row["id"], "to": neighbor}
                    for row in spec["cells"] for neighbor in row["neighbors"]
                    if row["id"] < neighbor],
                   key=lambda row: (row["from"], row["to"]))
    stats = deepcopy(cache_stats) if cache_stats is not None else {
        "loaded": [], "pending": 0, "resident_bytes": 0,
        "budget_bytes": spec["max_cache_bytes"]}
    require(type(stats) is dict and set(stats) ==
            {"loaded", "pending", "resident_bytes", "budget_bytes"}
            and type(stats["loaded"]) is list
            and all(type(name) is str and name in cells
                    for name in stats["loaded"])
            and type(stats["pending"]) is int
            and 0 <= stats["pending"] <= 8
            and type(stats["resident_bytes"]) is int
            and 0 <= stats["resident_bytes"] <= spec["max_cache_bytes"]
            and stats["budget_bytes"] == spec["max_cache_bytes"],
            "Invalid R54 cache telemetry")
    return {"focus": focus, "zoom": float(zoom), "cells": rows,
            "edges": links,
            "prefetch": prefetch_order(spec, focus),
            "cache": stats,
            "estimated_total_bytes": sum(r["estimated_bytes"] for r in rows),
            "excluded_scenes": sorted(set(project["exploration"]) -
                                      {r["scene"] for r in rows}),
            "note": "LOD and tile RAM are estimates; no GPU asset loads."}
