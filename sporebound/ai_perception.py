"""R37.D1: deterministic sight, sound and pursuit preview on canonical R35 grids.

Headless read-only sensor, not a new world simulation. Sight uses integer
supercover LOS; hearing follows R35's stable 4-neighbour path and verified
movement inputs. No graphics, random numbers, timers or NPC teleportation.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from .living_world_navigation import MAX_STAGE_CELLS, _point, shortest_path
from .model import require

FACING = {"north": (0, -1), "south": (0, 1),
          "west": (-1, 0), "east": (1, 0), "omni": (0, 0)}
SENSOR_FIELDS = {"version", "facing", "vision_range", "hearing_range"}
MAX_RANGE = 16


def validate_sensor(spec):
    """Strict v1 opt-in sensor; bool ranges and unknown keys fail closed."""
    require(type(spec) is dict and set(spec) == SENSOR_FIELDS
            and type(spec["version"]) is int and spec["version"] == 1
            and type(spec["facing"]) is str and spec["facing"] in FACING
            and type(spec["vision_range"]) is int
            and 1 <= spec["vision_range"] <= MAX_RANGE
            and type(spec["hearing_range"]) is int
            and 0 <= spec["hearing_range"] <= MAX_RANGE,
            "Invalid R37 sensor; expected facing and bounded sight/hearing")
    return deepcopy(spec)


def _clear_los(stage, start, end):
    """Integer supercover ray. Corner touches require BOTH side cells clear."""
    blocked = {tuple(cell) for cell in stage["blocked"]}
    x, y = start
    goal_x, goal_y = end
    dx, dy = abs(goal_x - x), abs(goal_y - y)
    sx = 1 if goal_x > x else -1 if goal_x < x else 0
    sy = 1 if goal_y > y else -1 if goal_y < y else 0
    ix = iy = 0
    while ix < dx or iy < dy:
        a = (1 + 2 * ix) * dy
        b = (1 + 2 * iy) * dx
        if a == b:
            if (x + sx, y) in blocked or (x, y + sy) in blocked:
                return False
            x, y = x + sx, y + sy
            ix += 1
            iy += 1
        elif a < b:
            x += sx
            ix += 1
        else:
            y += sy
            iy += 1
        if (x, y) in blocked:
            return False
    return True


def perceive_grid(stage, actor, target, sensor, *, movement=False,
                  remembered=None):
    """Inspect bounded geometry without modifying any live state.

    Movement is supplied from an independently validated movement journal.
    Remembered location is the replayed blackboard's last known position.
    """
    sensor = validate_sensor(sensor)
    require(type(stage) is dict and {"width", "height", "blocked"} <= set(stage)
            and type(stage["width"]) is int
            and type(stage["height"]) is int
            and 1 <= stage["width"] <= 32
            and 1 <= stage["height"] <= 32
            and stage["width"] * stage["height"] <= MAX_STAGE_CELLS
            and type(stage["blocked"]) is list
            and len(stage["blocked"]) <= MAX_STAGE_CELLS,
            "Invalid R37 canonical navigation grid")
    require(all(_point(p, stage) for p in (actor, target))
            and type(movement) is bool,
            "R37 perception needs clear actor/target cells and boolean movement")
    require(remembered is None or _point(remembered, stage),
            "Last-known target position is outside canonical walkable space")
    dx, dy = target[0] - actor[0], target[1] - actor[1]
    manhattan = abs(dx) + abs(dy)
    if sensor["facing"] == "omni":
        within_cone = True
    else:
        fx, fy = FACING[sensor["facing"]]
        forward = dx * fx + dy * fy
        lateral = abs(dx * fy - dy * fx)
        within_cone = forward > 0 and lateral <= forward
    within_range = manhattan <= sensor["vision_range"]
    clear = (_clear_los(stage, actor, target)
             if within_range and within_cone else False)
    visible = within_range and within_cone and clear
    path = shortest_path(stage, actor, target)
    audible = (movement and path is not None
               and len(path) - 1 <= sensor["hearing_range"])
    signal = "seen" if visible else "heard" if audible else "none"
    objective = target if signal != "none" else remembered
    pursuit = (shortest_path(stage, actor, objective)
               if objective is not None else None)
    reachable = pursuit is not None
    next_step = (pursuit[1] if pursuit is not None and len(pursuit) > 1
                 else None)
    report = {
        "version": 1, "actor": list(actor), "target": list(target),
        "facing": sensor["facing"], "distance": manhattan,
        "within_cone": within_cone, "within_vision_range": within_range,
        "los_clear": clear, "visible": visible,
        "movement_input": movement, "heard": audible, "signal": signal,
        "alert": signal != "none" or remembered is not None,
        "path": deepcopy(pursuit), "reachable": reachable,
        "next_step": next_step, "path_length": (
            len(pursuit) - 1 if pursuit is not None else None),
        "reason": (
            "visible" if visible else "audible_movement" if audible else
            "remembered_position" if remembered is not None else
            "no_perception"),
    }
    raw = json.dumps({"sensor": sensor, "report": report},
                     ensure_ascii=True, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    report["digest"] = sha256(raw).hexdigest()
    return report


__all__ = ["validate_sensor", "perceive_grid", "FACING"]
