"""R34.B: deterministic, bounded prefab binding onto R34.A room graphs.

A prefab is *metadata referencing* a canonical Content mission and/or GameProject
asset; this is a read-only proposal, not a second asset registry, a map merger,
or a GameSession owner. Physical door coordinates and instantiation are deferred.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import re
from typing import Any, Mapping

from .procgen import (
    MAX_BATCH, ProcGenError, ProcGenRecipe, _canonical, _fail, generate,
)

ROLES = frozenset(("entry", "normal", "goal", "exit", "key"))
MAX_PREFABS = 64
MAX_SEARCH_NODES = 20000


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        _fail("invalid_library", f"{label} must be a 1..64 character identifier")
    return value


def validate_library(library: Mapping[str, Any], *, content=None, project=None) -> dict:
    """Reject malformed inputs and unknown canonical references before generation."""
    if not isinstance(library, Mapping) or set(library) != {"schema_version", "prefabs"}:
        _fail("invalid_library", "library needs schema_version and prefabs")
    if type(library["schema_version"]) is not int or library["schema_version"] != 1:
        _fail("unsupported_library", "unsupported room-library version")
    raw = library["prefabs"]
    if type(raw) is not list or not 1 <= len(raw) <= MAX_PREFABS:
        _fail("invalid_library", f"library needs 1..{MAX_PREFABS} prefabs")
    ids = set()
    rows = []
    for item in raw:
        allowed = {"id", "roles", "biomes", "ports", "asset_id", "mission_id", "tags"}
        if not isinstance(item, Mapping) or set(item) - allowed or not {"id", "roles", "biomes", "ports"} <= set(item):
            _fail("invalid_library", "prefab requires id, roles, biomes and ports")
        name = _id(item["id"], "prefab id")
        if name.casefold() in ids:
            _fail("invalid_library", f"duplicate prefab id: {name}")
        ids.add(name.casefold())
        roles, biomes, ports = item["roles"], item["biomes"], item["ports"]
        if (type(roles) is not list or not roles or len(roles) > len(ROLES)
                or any(x not in ROLES for x in roles) or len(roles) != len(set(roles))):
            _fail("invalid_library", f"{name}: invalid roles")
        if type(biomes) is not list or not 1 <= len(biomes) <= 16:
            _fail("invalid_library", f"{name}: invalid biome list")
        biome_ids = [_id(x, "biome") for x in biomes]
        if len(set(biome_ids)) != len(biome_ids):
            _fail("invalid_library", f"{name}: duplicate biome")
        if type(ports) is not list or not 1 <= len(ports) <= 4:
            _fail("invalid_library", f"{name}: needs 1..4 logical door ports")
        port_ids = [_id(x, "door kind") for x in ports]
        if type(item.get("tags", [])) is not list or len(item.get("tags", [])) > 16:
            _fail("invalid_library", f"{name}: invalid tags")
        tags = [_id(x, "tag") for x in item.get("tags", [])]
        if len(set(tags)) != len(tags):
            _fail("invalid_library", f"{name}: duplicate tag")
        row = {"id": name, "roles": sorted(roles), "biomes": sorted(biome_ids),
               "ports": sorted(port_ids), "tags": sorted(tags)}
        if "mission_id" in item:
            mission_id = _id(item["mission_id"], "mission id")
            if content is None or mission_id not in getattr(content, "missions", {}):
                _fail("unknown_reference", f"{name}: unknown Content mission {mission_id}")
            row["mission_id"] = mission_id
        if "asset_id" in item:
            asset_id = _id(item["asset_id"], "asset id")
            if project is None:
                _fail("unknown_reference", f"{name}: GameProject required for {asset_id}")
            try:
                project.asset_registry().require_reference(asset_id, "sprite")
            except (ValueError, AttributeError, KeyError, TypeError) as exc:
                raise ProcGenError("unknown_reference",
                                   f"{name}: invalid sprite asset {asset_id}: {exc}") from exc
            row["asset_id"] = asset_id
        rows.append(row)
    rows.sort(key=lambda x: x["id"])
    return {"schema_version": 1, "prefabs": rows}


def demo_library() -> dict:
    """Read-only, unbound templates for previews, never claim actual map assets."""
    return {"schema_version": 1, "prefabs": [
        {"id": "entry", "roles": ["entry"], "biomes": ["ruins"],
         "ports": ["arch", "arch"]},
        {"id": "hall", "roles": ["normal"], "biomes": ["ruins"],
         "ports": ["arch", "arch", "arch", "arch"]},
        {"id": "keyroom", "roles": ["key"], "biomes": ["ruins"],
         "ports": ["arch", "arch"]},
        {"id": "boss", "roles": ["goal"], "biomes": ["ruins"],
         "ports": ["arch", "arch"]},
        {"id": "exit", "roles": ["exit"], "biomes": ["ruins"],
         "ports": ["arch", "arch"]},
    ]}


def _candidate_order(seed: int, room_id: int, candidates: list[dict]) -> list[dict]:
    return sorted(candidates, key=lambda p: (
        sha256(_canonical([seed, room_id, p["id"]])).hexdigest(), p["id"]))


def _bind_graph(rooms: list[dict], prefabs: list[dict], *, biome: str, seed: int,
                search_budget: int) -> tuple[dict, dict]:
    candidates = []
    for room in rooms:
        pool = [p for p in prefabs if room["role"] in p["roles"]
                and biome in p["biomes"] and len(p["ports"]) >= len(room["neighbors"])]
        if not pool:
            _fail("unsatisfiable_prefabs",
                  f"room {room['id']} ({room['role']}, degree {len(room['neighbors'])}) "
                  f"has no prefab in biome {biome}")
        candidates.append(_candidate_order(seed, room["id"], pool))

    selected: dict[int, dict] = {}
    available: dict[int, Counter] = {}
    edge_types: dict[tuple[int, int], str] = {}
    checked = 0
    exhausted = False

    def visit(room_id: int) -> bool:
        nonlocal checked, exhausted
        if room_id == len(rooms):
            return True
        previous = [other for other in rooms[room_id]["neighbors"] if other < room_id]
        for prefab in candidates[room_id]:
            checked += 1
            if checked > search_budget:
                exhausted = True
                return False
            selected[room_id] = prefab
            available[room_id] = Counter(prefab["ports"])
            allocated = []

            def connect(index: int) -> bool:
                if index == len(previous):
                    return visit(room_id + 1)
                other = previous[index]
                common = sorted((available[room_id] & available[other]).keys())
                for kind in common:
                    available[room_id][kind] -= 1
                    available[other][kind] -= 1
                    edge = (other, room_id)
                    edge_types[edge] = kind
                    allocated.append(edge)
                    if connect(index + 1):
                        return True
                    allocated.pop()
                    del edge_types[edge]
                    available[other][kind] += 1
                    available[room_id][kind] += 1
                return False

            if connect(0):
                return True
            del selected[room_id]
            del available[room_id]
            # State owned by earlier rooms is fully restored by connect().
            if exhausted:
                return False
        return False

    if not visit(0):
        _fail("search_budget_exhausted" if exhausted else "unsatisfiable_prefabs",
              "prefab socket matching has no solution within the deterministic budget")
    return selected, edge_types


def generate_with_prefabs(recipe: ProcGenRecipe | Mapping[str, Any],
                          library: Mapping[str, Any], *, biome: str,
                          content=None, project=None, search_budget: int = MAX_SEARCH_NODES) -> dict:
    """Materialize an immutable-by-copy *proposal*, never mutate Content/GameProject.

    Ports are logical socket labels. The result does not imply compass-facing
    doors, a collision-safe physical tilemap, or a runnable combat encounter.
    """
    if not isinstance(recipe, ProcGenRecipe):
        recipe = ProcGenRecipe.from_dict(recipe)
    recipe.validate()
    biome = _id(biome, "selected biome")
    if type(search_budget) is not int or not 1 <= search_budget <= MAX_SEARCH_NODES:
        _fail("invalid_budget", "search_budget must be 1..20000")
    normalized = validate_library(library, content=content, project=project)
    layout = generate(recipe)
    selected, edges = _bind_graph(layout["rooms"], normalized["prefabs"], biome=biome,
                                  seed=recipe.seed, search_budget=search_budget)
    for room in layout["rooms"]:
        prefab = selected[room["id"]]
        room["prefab_id"] = prefab["id"]
        room["biome"] = biome
        room["asset_id"] = prefab.get("asset_id")
        room["mission_id"] = prefab.get("mission_id")
        room["doors"] = [
            {"to": other, "kind": edges[(min(other, room["id"]), max(other, room["id"]))]}
            for other in room["neighbors"]
        ]
    base_digest = layout.pop("digest")
    layout["base_digest"] = base_digest
    layout["library_digest"] = sha256(_canonical(normalized)).hexdigest()
    layout["biome"] = biome
    layout["digest"] = sha256(_canonical(layout)).hexdigest()
    return layout


def verify_with_prefabs(recipe: ProcGenRecipe | Mapping[str, Any],
                        library: Mapping[str, Any], layout: Mapping[str, Any], *,
                        biome: str, content=None, project=None) -> bool:
    expected = generate_with_prefabs(recipe, library, biome=biome,
                                     content=content, project=project)
    if not isinstance(layout, Mapping) or dict(layout) != expected:
        _fail("invalid_generation", "prefab layout or its source fingerprint changed")
    return True


def preview_seeds(recipe: ProcGenRecipe | Mapping[str, Any],
                  library: Mapping[str, Any], seeds: list[int], *, biome: str,
                  content=None, project=None) -> list[dict]:
    """Failures are explicit, seed-indexed counterexamples; never silently skipped."""
    if not isinstance(recipe, ProcGenRecipe):
        recipe = ProcGenRecipe.from_dict(recipe)
    recipe.validate()
    if type(seeds) is not list or not 1 <= len(seeds) <= MAX_BATCH:
        _fail("invalid_budget", "seed batch must contain 1..500 integers")
    normalized = validate_library(library, content=content, project=project)
    reports = []
    from dataclasses import replace
    for seed in seeds:
        try:
            candidate = replace(recipe, seed=seed)
            result = generate_with_prefabs(candidate, normalized, biome=biome,
                                           content=content, project=project)
            reports.append({"seed": seed, "passed": True, "digest": result["digest"],
                            "route": result["route"], "rooms": len(result["rooms"])})
        except ProcGenError as exc:
            reports.append({"seed": seed, "passed": False,
                            "error_code": exc.code, "message": str(exc)})
    return reports
