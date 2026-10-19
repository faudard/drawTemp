"""R29.B bounded, read-only action-adventure reachability and replay evidence.

This is static puzzle exploration over R26's authored scene *subset*, never a
replacement for ActionRuntime or a proof about enemy AI, physics or full saves.
All conclusions include a witness; time/state budgets are fail-closed.
"""
from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from hashlib import sha256
import json

MAX_STATES = 200_000
MAX_OBJECTS = 12
DIRECTIONS = ((0, -1), (-1, 0), (1, 0), (0, 1))


def _sha(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _validate(scene, goals, budget):
    if type(budget) is not int or not 1 <= budget <= MAX_STATES:
        raise ValueError("State budget must be 1..200000")
    if type(scene) is not dict or set(scene) != {
            "id", "width", "height", "walls", "hero", "enemies", "objects"}:
        raise ValueError("Expected an R26 action scene with exact keys")
    w, h = scene["width"], scene["height"]
    if type(w) is not int or type(h) is not int or not (3 <= w <= 128 and 3 <= h <= 128):
        raise ValueError("Invalid scene dimensions")
    if type(scene["id"]) is not str or not scene["id"]:
        raise ValueError("Scene ID missing")

    def valid_cell(cell):
        return (type(cell) is list and len(cell) == 2 and
                all(type(n) is int for n in cell) and 0 <= cell[0] < w and 0 <= cell[1] < h)

    if type(scene["walls"]) is not list or not all(valid_cell(p) for p in scene["walls"]):
        raise ValueError("Invalid wall cells")
    walls = {tuple(p) for p in scene["walls"]}
    if len(walls) != len(scene["walls"]):
        raise ValueError("Duplicate wall")
    hero = scene["hero"]
    if type(hero) is not dict or set(hero) != {"pos", "hp"} or not valid_cell(hero["pos"]) or tuple(hero["pos"]) in walls:
        raise ValueError("Invalid player spawn")
    if type(hero["hp"]) is not int or not 1 <= hero["hp"] <= 100:
        raise ValueError("Invalid hero HP")
    if type(scene["enemies"]) is not list or type(scene["objects"]) is not list:
        raise ValueError("Invalid actor/object lists")
    if len(scene["objects"]) > MAX_OBJECTS:
        raise ValueError("Static solver is limited to 12 interactive objects")
    objects = {}
    for obj in scene["objects"]:
        if (type(obj) is not dict or set(obj) != {"id", "kind", "pos", "item", "requires"}
                or type(obj["id"]) is not str or not obj["id"] or obj["id"] in objects
                or obj["kind"] not in ("chest", "door", "sign")
                or not valid_cell(obj["pos"]) or tuple(obj["pos"]) in walls
                or type(obj["item"]) is not str or type(obj["requires"]) is not str
                or (obj["kind"] == "chest" and not obj["item"])):
            raise ValueError("Invalid or duplicate interaction object")
        objects[obj["id"]] = obj
    if type(goals) is not list or not goals or len(goals) > 32 or not all(valid_cell(x) for x in goals):
        raise ValueError("Explicit nonempty cell goals required")
    if len({tuple(g) for g in goals}) != len(goals):
        raise ValueError("Duplicate goals")
    return walls, sorted(objects.values(), key=lambda obj: obj["id"])


def analyze_action_scene(scene, goals, *, state_budget=50000):
    """Explore every reachable (cell, opened objects, inventory) until budget.

    Multiple goals are individually checked; reaching *any* goal ends a route.
    A dead end is a reachable nonterminal state that cannot reach ANY goal,
    including after spending a key on the wrong door. Movement is orthogonal
    and interactions are within 1 tile (R26 range 1600 millitiles). The
    abstract solver ignores animation, timing, damage, enemy AI and collisions
    at intermediate continuous positions. A static success is NOT a gameplay
    certification, especially for scenes containing enemies.
    """
    walls, objects = _validate(scene, goals, state_budget)
    goal_set = {tuple(g) for g in goals}
    door_cells = {tuple(o["pos"]): i for i, o in enumerate(objects)
                  if o["kind"] == "door"}

    def available(cell, opened):
        x, y = cell
        if not (0 <= x < scene["width"] and 0 <= y < scene["height"]) or cell in walls:
            return False
        index = door_cells.get(cell)
        return index is None or bool(opened & (1 << index))

    if not available(tuple(scene["hero"]["pos"]), 0):
        raise ValueError("Hero spawn is blocked by a closed door")
    # Inventory counts are bounded by one reward per chest, no infinite loops.
    inventory_ids = sorted({o["item"] for o in objects if o["kind"] == "chest"}
                           | {o["requires"] for o in objects if o["requires"]})
    item_index = {name: n for n, name in enumerate(inventory_ids)}
    initial = (tuple(scene["hero"]["pos"]), 0, (0,) * len(inventory_ids))
    queue, parent = deque([initial]), {initial: None}
    reverse, terminals = defaultdict(list), set()
    found = {}
    exhausted = False
    saturated = False

    def add(previous, successor, action):
        nonlocal saturated
        if successor in parent:
            return
        if len(parent) >= state_budget:
            saturated = True
            return
        parent[successor] = (previous, action)
        reverse[successor].append(previous)
        queue.append(successor)

    def path(state):
        commands = []
        while parent[state] is not None:
            previous, action = parent[state]
            commands.append(action)
            state = previous
        return list(reversed(commands))

    processed = 0
    while queue:
        if processed >= state_budget:
            exhausted = True
            break
        state = queue.popleft()
        processed += 1
        cell, opened, inv = state
        if cell in goal_set:
            found.setdefault(cell, path(state))
            terminals.add(state)
            continue
        x, y = cell
        for i, obj in enumerate(objects):
            # Each object is unique and may be interacted with at most once.
            if obj["kind"] == "sign" or opened & (1 << i):
                continue
            ox, oy = obj["pos"]
            if (ox - x) ** 2 + (oy - y) ** 2 > 2:
                continue
            needed = obj["requires"]
            if needed and inv[item_index[needed]] == 0:
                continue
            new_inv = list(inv)
            if needed and obj["kind"] == "door":
                new_inv[item_index[needed]] -= 1
            if obj["kind"] == "chest":
                new_inv[item_index[obj["item"]]] += 1
            nxt = (cell, opened | (1 << i), tuple(new_inv))
            # Register all reverse edges, even if successor visited earlier.
            reverse[nxt].append(state)
            add(state, nxt, {"kind": "interact", "id": obj["id"]})
        for dx, dy in DIRECTIONS:
            target = (x + dx, y + dy)
            if not available(target, opened):
                continue
            nxt = (target, opened, inv)
            reverse[nxt].append(state)
            add(state, nxt, {"kind": "move", "to": list(target)})
    # Saturation is inconclusive even when the current frontier contains no
    # counterexample; silently pruning at exactly the cap would be unsound.
    if len(parent) >= state_budget and queue:
        exhausted = True
    complete = not exhausted and not saturated and not queue
    solvable = set(terminals)
    backwards = deque(terminals)
    while backwards:
        for predecessor in reverse[backwards.popleft()]:
            if predecessor not in solvable:
                solvable.add(predecessor)
                backwards.append(predecessor)
    dead = [s for s in parent if s not in solvable] if complete else []
    missing = [goal for goal in goals if tuple(goal) not in found] if complete else []
    cases = [{"at": list(s[0]), "inventory": {
        name: s[2][i] for i, name in enumerate(inventory_ids) if s[2][i]},
        "opened": [o["id"] for i, o in enumerate(objects) if s[1] & (1 << i)],
        "witness": path(s)} for s in dead[:3]]
    limitations = ["continuous movement/collision and frame timing not simulated",
                   "narrative/save/hybrid transitions not evaluated"]
    if scene["enemies"]:
        limitations.append("enemy AI, enemy collisions and combat outcomes not modelled")
    status = ("inconclusive" if not complete else
              "softlock_risk" if dead or missing else "static_reachable")
    return {
        "schema": 1, "kind": "r29b-action-static-puzzle",
        "scene": scene["id"], "scene_sha256": _sha(scene), "status": status,
        "complete": complete, "states_explored": processed,
        "state_budget": state_budget, "goal_policy": "any goal exits the route; every goal audited",
        "reachable_goals": [{"cell": list(g), "witness": found[g]}
                            for g in sorted(found)],
        "unreachable_goals": deepcopy(missing),
        "dead_end_states": len(dead) if complete else None,
        "counterexamples": cases, "limitations": limitations,
        "runtime_certified": False,
    }


def audit_action_replay(scene, commands, *, checkpoint_every=5):
    """Compare real R26 uninterrupted replay and every disk-style checkpoint.

    Returns blocked when the R26 module is not in the checked out revision;
    absence must never be replaced by a fake simulator.
    """
    if type(checkpoint_every) is not int or not 1 <= checkpoint_every <= 1000:
        raise ValueError("Invalid checkpoint interval")
    if type(commands) is not list or not 1 <= len(commands) <= 2000:
        raise ValueError("Replay command count must be 1..2000")
    try:
        from sporebound.action_runtime import ActionRuntime
    except ModuleNotFoundError as exc:
        if exc.name not in ("sporebound.action_runtime", "sporebound"):
            raise
        return {"status": "blocked", "reason": "R26 ActionRuntime not in this revision",
                "replay_verified": False, "runtime_certified": False}
    runner = ActionRuntime(scene)
    witnesses = []
    for index, command in enumerate(deepcopy(commands), 1):
        runner.step(command)
        if index % checkpoint_every == 0 or index == len(commands):
            before = runner.digest()
            restored = ActionRuntime.from_recording(runner.recording(), expected_scene=scene)
            if restored.digest() != before or restored.recording() != runner.recording():
                raise ValueError("R26 restored checkpoint diverged at tick " + str(index))
            witnesses.append({"tick": index, "digest": before})
    final = runner.recording()
    again = ActionRuntime.from_recording(final, expected_scene=scene)
    if again.digest() != runner.digest():
        raise ValueError("R26 deterministic replay mismatch")
    return {"status": "partial", "replay_verified": True,
            "scene_sha256": _sha(scene), "final_digest": runner.digest(),
            "ticks": runner.tick, "checkpoints": witnesses,
            "runtime_certified": False,
            "scope": "single R26 scene: tick/order/checkpoint parity; no hybrid GameSession"}


def audit_dungeon_puzzle(dungeon, *, state_budget=50000):
    """Adapt real R27 DungeonStudio.puzzle_report without elevating its scope."""
    if type(state_budget) is not int or not 1 <= state_budget <= 200_000:
        raise ValueError("Invalid puzzle budget")
    report = dungeon.puzzle_report(state_budget=state_budget)
    required = {"complete", "unreachable_goals", "unreachable_objects", "warnings", "states"}
    if type(report) is not dict or not required <= report.keys() or type(report["complete"]) is not bool:
        raise ValueError("R27 puzzle_report contract incomplete")
    if any(type(report[k]) is not list for k in ("unreachable_goals", "unreachable_objects", "warnings")):
        raise ValueError("R27 puzzle_report contains invalid evidence")
    if type(report["states"]) is not int or report["states"] < 0:
        raise ValueError("Invalid R27 state count")
    status = ("inconclusive" if not report["complete"] else "softlock_risk"
              if report["unreachable_goals"] or report["unreachable_objects"] else "static_reachable")
    return {"schema": 1, "kind": "r29b-r27-puzzle-audit", "status": status,
            "complete": report["complete"], "states_explored": report["states"],
            "unreachable_goals": deepcopy(report["unreachable_goals"]),
            "unreachable_objects": deepcopy(report["unreachable_objects"]),
            "warnings": deepcopy(report["warnings"]), "runtime_certified": False,
            "limitations": ["R27 static cell/lever model only; not CT combat/AI",
                            "no crash recovery or Player walkthrough proof"]}
