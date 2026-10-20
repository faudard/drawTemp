"""R36.B3 — read-only R32 authoritative AABB collision contact projection.

Unlike visual animation markers, these records originate solely in successful
PlatformPhysics.step() collision events. Exact fixed-point contact *faces* are
derived from the validated canonical collider AABBs and post-step actor body.
Never feed this module back into collision/damage code.
"""
from __future__ import annotations

from copy import deepcopy

from sporebound.platform_physics import (
    SCALE, TICK_HZ, PlatformPhysics, validate_platform_scene,
)

CONTACT_EVENTS = frozenset(("wall", "land", "ceiling"))
MAX_EVENTS = 64


def trace_platform_contacts(scene, snapshot, events):
    """Return provenance + exact AABB face coordinates or reject inconsistent data.

    The input must be the immediately committed R32 snapshot and event list.
    Detection, obstacle disabling, moving-platform sweeps and one-way behavior
    remain owned by PlatformPhysics; no graphical marker can create a hit.
    """
    scene = validate_platform_scene(scene)
    if (type(snapshot) is not dict or snapshot.get("scene") != scene["id"] or
            type(snapshot.get("tick")) is not int or
            snapshot.get("tick_hz") != TICK_HZ or
            type(events) not in (tuple, list) or len(events) > MAX_EVENTS):
        raise ValueError("Contact tracing requires a bounded committed R32 step")
    body = snapshot.get("actor")
    if (type(body) is not dict or type(body.get("x")) is not int or
            type(body.get("y")) is not int):
        raise ValueError("R32 contact snapshot contains no valid actor")
    x, y = body["x"], body["y"]
    w, h = scene["hero"]["size"]
    if not 0 <= x <= scene["width"] - w or not 0 <= y <= scene["height"] - h:
        raise ValueError("Contact actor is outside the authored world")
    lookup = {row["id"]: row for row in scene["colliders"]}
    disabled = snapshot.get("disabled_colliders")
    movers = snapshot.get("movers")
    if type(disabled) is not list or type(movers) is not dict:
        raise ValueError("R32 snapshot is missing collider state")
    result = []
    for index, event in enumerate(events):
        if (type(event) is not dict or event.get("tick") != snapshot["tick"]
                or type(event.get("tick")) is not int or
                type(event.get("kind")) is not str):
            raise ValueError("Contact event does not match committed tick")
        kind = event["kind"]
        if kind not in CONTACT_EVENTS:
            continue
        collider_id = event.get("collider")
        if type(collider_id) is not str or not collider_id:
            raise ValueError("AABB collision event lacks a collider")
        if collider_id == "world":
            box = [0, 0, scene["width"], scene["height"]]
            if kind == "wall":
                if x == 0:
                    point, normal = [0, y + h // 2], [1, 0]
                elif x + w == scene["width"]:
                    point, normal = [scene["width"], y + h // 2], [-1, 0]
                else:
                    raise ValueError("World wall is not in contact with actor")
            elif kind == "land":
                if y + h != scene["height"]:
                    raise ValueError("World floor does not touch actor")
                point, normal = [x + w // 2, scene["height"]], [0, -1]
            else:
                if y != 0:
                    raise ValueError("World ceiling does not touch actor")
                point, normal = [x + w // 2, 0], [0, 1]
        else:
            spec = lookup.get(collider_id)
            if spec is None or collider_id in disabled or spec["trigger"]:
                raise ValueError("R32 contact refers to non-solid or disabled collider")
            box = list(spec["rect"])
            if collider_id in movers:
                mover = movers[collider_id]
                if type(mover) is not dict or type(mover.get("x")) is not int:
                    raise ValueError("Moving platform has invalid committed position")
                box[0] = mover["x"]
            bx, by, bw, bh = box
            if kind == "wall":
                if not (y < by + bh and by < y + h):
                    raise ValueError("Wall faces do not vertically overlap")
                mid = (max(y, by) + min(y + h, by + bh)) // 2
                if x + w == bx:
                    point, normal = [bx, mid], [-1, 0]
                elif x == bx + bw:
                    point, normal = [x, mid], [1, 0]
                else:
                    raise ValueError("Wall contact is not on the collider face")
            else:
                if not (x < bx + bw and bx < x + w):
                    raise ValueError("Contact faces do not horizontally overlap")
                mid = (max(x, bx) + min(x + w, bx + bw)) // 2
                if kind == "land" and y + h == by:
                    point, normal = [mid, by], [0, -1]
                elif kind == "ceiling" and y == by + bh:
                    point, normal = [mid, y], [0, 1]
                else:
                    raise ValueError("Vertical contact is not on the collider face")
        result.append({
            "id": f'{snapshot["tick"]}:{index}:{collider_id}',
            "tick": snapshot["tick"], "kind": kind,
            "collider": collider_id, "contact": point,
            "normal": normal, "collider_rect": box,
            "world_xy": [point[0] / SCALE, point[1] / SCALE],
            "origin": "r32_committed_collision",
        })
    return deepcopy(result)


def trace_committed_platform_step(runtime):
    """Safe public entry: read the engine's own successful step event log.

    Pure trace_platform_contacts() is suitable for trusted detached snapshots;
    this entrypoint additionally ties it to a real PlatformPhysics instance.
    """
    if not isinstance(runtime, PlatformPhysics):
        raise ValueError("Expected authoritative R32 PlatformPhysics instance")
    return trace_platform_contacts(
        runtime.scene, runtime.snapshot(), runtime.last_events)
