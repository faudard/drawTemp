"""R35.C1: read-only schedule debugger, using authoritative LivingWorld state."""
from copy import deepcopy

from .model import require


def timeline(world, flags, *, scene=None, limit=512):
    """Project one day's authored transitions, not a historical event replay.

    Conditional stops use the current Campaign flags; this is a forecast.
    A bounded deterministic list is produced even for 256 densely scheduled NPCs.
    """
    require(type(flags) is dict, "Timeline requires canonical campaign flags")
    require(scene is None or scene in world.scene_ids, "Unknown timeline scene")
    require(type(limit) is int and 1 <= limit <= 2048,
            "Timeline limit must be 1..2048")
    rows = []
    for npc in world.spec["npcs"]:
        for stop in npc["schedule"]:
            condition = stop.get("when")
            if condition is not None and (
                    flags.get(condition["flag"], False) is not condition["eq"]):
                continue
            if scene is not None and stop["scene"] != scene:
                continue
            rows.append({
                "minute": stop["minute"], "kind": "npc_stop",
                "id": npc["id"], "scene": stop["scene"],
                "activity": stop["activity"]})
    for quest in world.spec.get("daily_quests", []):
        for kind, minute in (("quest_open", quest["start_minute"]),
                             ("quest_close", quest["end_minute"])):
            rows.append({"minute": minute, "kind": kind, "id": quest["id"]})
    # These are authored transition times, not replayed player commands.
    rows.sort(key=lambda r: (r["minute"], r["kind"], r["id"]))
    return {
        "version": 1, "day": world.day, "preview_only": True,
        "current_minute": world.minute, "total": len(rows),
        "truncated": len(rows) > limit, "entries": deepcopy(rows[:limit]),
        "active": world.view(flags, scene=scene),
    }
