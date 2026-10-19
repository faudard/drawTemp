"""R35.D2: explicit, bounded and deterministic cross-scene NPC portal legs.

A portal joins *authored exploration cells*, never a tactical mission.
During a transfer an NPC leaves its origin at the portal, has no current
scene for travel_minutes, then re-enters at the target portal. No hidden
world transition event or offscreen mutable actor database is needed.
"""
from __future__ import annotations

from .model import require
from .living_world_navigation import _point, shortest_path

MAX_TRANSFERS = 64
MAX_TRANSIT_MINUTES = 240


def _ident(value):
    return (type(value) is str and 1 <= len(value) <= 64
            and all(c.isascii() and (c.isalnum() or c in "_-") for c in value))


def compile_legs(spec, exploration):
    """Validate and index immutable authored leg geometry once per world.

    Indexed by (NPC ID, departure stop minute). Explicit transfer documents
    are complete, never a permissive mix of defined and silent teleport hops.
    """
    require(type(exploration) is dict, "Missing exploration scene geometry")
    transfers = spec.get("transfers", [])
    require(type(transfers) is list and len(transfers) <= MAX_TRANSFERS,
            "Invalid living-world transfer catalogue")
    links = {}
    for item in transfers:
        require(type(item) is dict and set(item) ==
                {"id", "from_scene", "to_scene", "from_pos", "to_pos",
                 "travel_minutes"}, "Invalid transfer fields")
        source = item["from_scene"]
        target = item["to_scene"]
        require(_ident(item["id"]) and source != target
                and type(source) is str and type(target) is str
                and source in exploration and target in exploration
                and type(item["travel_minutes"]) is int
                and 1 <= item["travel_minutes"] <= MAX_TRANSIT_MINUTES
                and _point(item["from_pos"], exploration[source])
                and _point(item["to_pos"], exploration[target]),
                "Invalid scene transfer gateway, position or duration")
        key = (source, target)
        require(key not in links
                and all(other["id"] != item["id"] for other in links.values()),
                "Duplicate transfer ID or direction")
        links[key] = item
    routes = {}
    path_cache = {}
    def route(scene, start, finish):
        key = (scene, tuple(start), tuple(finish))
        if key not in path_cache:
            path_cache[key] = shortest_path(exploration[scene], start, finish)
        return path_cache[key]

    for npc in spec["npcs"]:
        stops = npc["schedule"]
        if not any("pos" in row for row in stops):
            continue
        require(all("pos" in row for row in stops),
                "NPC navigation requires positions at every stop")
        for idx, source in enumerate(stops):
            target = stops[(idx + 1) % len(stops)]
            duration = (target["minute"] - source["minute"]) % 1440 or 1440
            if source["scene"] == target["scene"]:
                path = route(source["scene"], source["pos"], target["pos"])
                require(path is not None and len(path)-1 <= duration,
                        "NPC local route exceeds its schedule or cannot be reached")
                leg = {"kind": "local", "path": path, "steps": len(path)-1}
            else:
                portal = links.get((source["scene"], target["scene"]))
                if portal is None:
                    require("transfers" not in spec,
                            "NPC cross-scene leg has no authored transfer")
                    leg = {"kind": "legacy_handoff"}
                else:
                    first = route(source["scene"], source["pos"],
                                  portal["from_pos"])
                    last = route(target["scene"], portal["to_pos"],
                                 target["pos"])
                    require(first is not None and last is not None,
                            "NPC transfer portal is unreachable from its schedule")
                    steps = (len(first)-1 + portal["travel_minutes"]
                             + len(last)-1)
                    require(steps <= duration,
                            "NPC cross-scene trip cannot finish before its next stop")
                    leg = {"kind": "transfer", "first": first, "last": last,
                           "transit": portal["travel_minutes"],
                           "steps": steps,
                           "target_scene": target["scene"],
                           "transfer_id": portal["id"]}
            routes[(npc["id"], source["minute"])] = leg
    return routes


def project_leg(prior, target, route, minute, arrival, activity):
    """Pure calendar projection: origin / transit / target within one leg."""
    result = {"scene": prior["scene"], "activity": activity,
              "pos": list(prior["pos"]), "moving": False}
    if route["kind"] == "legacy_handoff":
        result["handoff_pending"] = True
        return result
    duration = route["steps"]
    depart = arrival - duration
    if minute <= depart or duration == 0:
        return result
    elapsed = min(duration, minute - depart)
    if route["kind"] == "local":
        result["pos"] = list(route["path"][elapsed])
        result["moving"] = elapsed < duration
        if elapsed < duration:
            result["activity"] = "travel"
        else:
            result["activity"] = target["activity"]
        return result
    first = len(route["first"]) - 1
    transit = route["transit"]
    if elapsed <= first:
        result["pos"] = list(route["first"][elapsed])
    elif elapsed < first + transit:
        result["scene"] = None
        result["pos"] = None
    else:
        result["scene"] = route["target_scene"]
        progress = elapsed - first - transit
        result["pos"] = list(route["last"][progress])
    result["moving"] = elapsed < duration
    if elapsed < duration:
        result["activity"] = "travel"
    else:
        result["activity"] = target["activity"]
    result["transfer_id"] = route["transfer_id"]
    return result


__all__ = ["compile_legs", "project_leg"]
