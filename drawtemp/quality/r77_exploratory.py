"""R77.A: bounded, deterministic exploratory QA against the real R26 runtime.

Read-only with respect to authored data. A static R29.B softlock witness is an
*abstract risk*, not proof that the Player is softlocked. A successful agent
replay is headless evidence only, never a multi-genre or release certification.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from hashlib import sha256
import json
from random import Random

from drawtemp.quality.r29b_gameplay import analyze_action_scene
from sporebound.action_runtime import ActionRuntime, validate_scene

MAX_SEEDS = 8
MAX_TICKS_PER_SEED = 512
MAX_TOTAL_TICKS = 4096
DIRECTIONS = ((0, -1), (-1, 0), (1, 0), (0, 1))


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _cell(position):
    return position[0] // 1000, position[1] // 1000


def _routes(start, *, width, height, blocked):
    """One bounded BFS per tick, reused for every candidate destination."""
    queue, previous, distance = deque([start]), {start: None}, {start: 0}
    while queue:
        cell = queue.popleft()
        for dx, dy in DIRECTIONS:
            nxt = cell[0] + dx, cell[1] + dy
            if (nxt not in previous and nxt not in blocked and
                    0 <= nxt[0] < width and 0 <= nxt[1] < height):
                previous[nxt] = cell
                distance[nxt] = distance[cell] + 1
                queue.append(nxt)
    return previous, distance


def _next_input(runner, goals, rng, attempted):
    state = runner.snapshot()
    hero = state["hero"]
    cell = _cell(hero["pos"])
    enemies = state["enemies"]
    objects = state["objects"]
    # Only authored IDs are emitted; signs have no persistent opened state.
    for row in sorted(runner.scene["objects"], key=lambda obj: obj["id"]):
        ident = row["id"]
        distance = sum((hero["pos"][i] - (row["pos"][i] * 1000 + 500)) ** 2
                       for i in (0, 1))
        attempt = (ident, bool(row["requires"] and state["inventory"].get(row["requires"], 0)))
        if (row["kind"] != "sign" and attempt not in attempted and
                not objects[ident]["opened"] and distance <= 1100 ** 2):
            attempted.add(attempt)  # A newly acquired key permits a retry.
            return {"tick": runner.tick + 1, "interact": ident}

    blocked = {tuple(pos) for pos in runner.scene["walls"]}
    blocked.update(tuple(row["pos"]) for row in runner.scene["objects"]
                   if row["kind"] == "door" and not objects[row["id"]]["opened"])
    candidates = [(tuple(goal), "goal") for goal in goals]
    for row in runner.scene["objects"]:
        attempt = (row["id"], bool(row["requires"] and
                 state["inventory"].get(row["requires"], 0)))
        if (row["kind"] == "sign" or attempt in attempted or
                objects[row["id"]]["opened"]):
            continue
        pos = tuple(row["pos"])
        if row["kind"] == "door":
            candidates.extend(((pos[0] + dx, pos[1] + dy), "object")
                              for dx, dy in DIRECTIONS)
        else:
            candidates.append((pos, "object"))
    rng.shuffle(candidates)
    parents, distances = _routes(cell, width=runner.scene["width"],
                                 height=runner.scene["height"], blocked=blocked)
    choices = [(distances[target], target) for target, kind in candidates
               if target in distances and (kind == "object" or cell != target)]
    if choices:
        target = min(choices, key=lambda item: item[0])[1]
        next_cell = target
        while parents[next_cell] is not None and parents[next_cell] != cell:
            next_cell = parents[next_cell]
    else:
        open_cells = [(x, y) for y in range(runner.scene["height"])
                      for x in range(runner.scene["width"])
                      if (x, y) not in blocked]
        next_cell = rng.choice(open_cells) if open_cells else cell
    # Integer fixed-tick input, one axis at a time; collisions stay canonical.
    diff = [next_cell[i] * 1000 + 500 - hero["pos"][i] for i in (0, 1)]
    axis = 0 if abs(diff[0]) >= abs(diff[1]) else 1
    move = [0, 0]
    if abs(diff[axis]) >= 100:
        move[axis] = 1 if diff[axis] > 0 else -1
    nearby = any(enemy["hp"] > 0 and sum(
        (enemy["pos"][i] - hero["pos"][i]) ** 2 for i in (0, 1)) < 1600 ** 2
        for enemy in enemies.values())
    return {"tick": runner.tick + 1, "dx": move[0], "dy": move[1],
            "attack": bool(nearby and rng.randrange(4) == 0),
            "guard": bool(nearby and rng.randrange(3) == 0)}


def _run_seed(scene, goals, seed, ticks):
    runner, rng = ActionRuntime(deepcopy(scene)), Random(seed)
    attempted, cells, conditions, actions, reached = set(), set(), set(), set(), set()
    failures, event_kinds = [], set()
    outcome = "budget_exhausted"
    cells.add(_cell(runner.hero["pos"]))
    for _ in range(ticks):
        if _cell(runner.hero["pos"]) in goals:
            reached.add(_cell(runner.hero["pos"]))
            outcome = "goal_reached"
            break
        if not runner.hero["alive"]:
            outcome = "hero_dead"
            break
        cmd = _next_input(runner, goals, rng, attempted)
        try:
            events = runner.step(deepcopy(cmd))
        except Exception as exc:
            failures.append({"tick": cmd["tick"], "command": cmd,
                             "error_type": type(exc).__name__,
                             "message": str(exc)[:250]})
            outcome = "runtime_exception"
            break
        # Only successfully executed commands count toward action coverage.
        if cmd.get("interact"):
            actions.add("interact")
        elif cmd.get("attack"):
            actions.add("attack")
        elif cmd.get("dx") or cmd.get("dy"):
            actions.add("move")
        else:
            actions.add("idle")
        event_kinds.update(event["kind"] for event in events)
        snap = runner.snapshot()
        cells.add(_cell(snap["hero"]["pos"]))
        conditions.update("opened:" + name for name, row in snap["objects"].items()
                          if row["opened"])
        conditions.update("item:" + name for name, quantity in snap["inventory"].items()
                          if quantity > 0)
        conditions.update("defeated:" + name for name, enemy in snap["enemies"].items()
                          if enemy["hp"] == 0)
        if not snap["hero"]["alive"]:
            conditions.add("hero_dead")
        if _cell(snap["hero"]["pos"]) in goals:
            reached.add(_cell(snap["hero"]["pos"]))
            outcome = "goal_reached"
            break
    trace = runner.recording()
    try:
        restored = ActionRuntime.from_recording(trace, expected_scene=scene)
        replay_verified = restored.digest() == runner.digest()
    except Exception as exc:
        replay_verified = False
        failures.append({"tick": runner.tick, "error_type": type(exc).__name__,
                         "message": "Replay verification failed: " + str(exc)[:200]})
        outcome = "runtime_exception"
    if not replay_verified and not failures:
        failures.append({"tick": runner.tick, "error_type": "ReplayMismatch",
                         "message": "Reconstructed final digest differs"})
        outcome = "runtime_exception"
    return {"seed": seed, "outcome": outcome, "ticks": runner.tick,
            "goals_reached": [list(g) for g in sorted(reached)],
            "zones": [list(g) for g in sorted(cells)],
            "conditions": sorted(conditions), "actions": sorted(actions),
            "events": sorted(event_kinds), "trace": trace["commands"],
            "trace_sha256": _digest(trace["commands"]),
            "final_state_sha256": runner.digest(), "replay_verified": replay_verified,
            "failures": failures}


def explore_action_scene(scene, goals, *, seeds=(0, 1, 2),
                         ticks_per_seed=128, state_budget=20000):
    """Bounded real-runtime rollouts and static R29.B analysis, without writes.

    A static counterexample is abstract: never conflate with Player softlock.
    """
    if (type(seeds) not in (tuple, list) or not 1 <= len(seeds) <= MAX_SEEDS or
            any(type(s) is not int or not 0 <= s <= 0xFFFFFFFF for s in seeds) or
            len(set(seeds)) != len(seeds)):
        raise ValueError("Provide 1..8 unique 32-bit nonnegative seeds")
    if (type(ticks_per_seed) is not int or not 1 <= ticks_per_seed <= MAX_TICKS_PER_SEED or
            len(seeds) * ticks_per_seed > MAX_TOTAL_TICKS):
        raise ValueError("Rollout tick budget exceeded")
    if type(state_budget) is not int or not 1 <= state_budget <= 200000:
        raise ValueError("Static state budget must be 1..200000")
    source = validate_scene(scene)  # canonical validation; detached copy
    source_hash = _digest(source)
    static = analyze_action_scene(deepcopy(source), deepcopy(goals), state_budget=state_budget)
    ordered_goals = {tuple(cell) for cell in goals}
    runs = [_run_seed(source, ordered_goals, seed, ticks_per_seed) for seed in seeds]
    if source_hash != _digest(source) or source_hash != _digest(scene):
        raise ValueError("Exploration modified authored data")
    all_zones = {tuple(cell) for run in runs for cell in run["zones"]}
    all_goals = {tuple(cell) for run in runs for cell in run["goals_reached"]}
    conditions = {name for run in runs for name in run["conditions"]}
    actions = {name for run in runs for name in run["actions"]}
    failures = [dict(seed=run["seed"], **failure) for run in runs
                for failure in run["failures"]]
    status = ("runtime_exception" if failures else
              "inconclusive" if not static["complete"] else
              "abstract_softlock_risk" if static["status"] == "softlock_risk" else
              "partial")
    return {"schema": 1, "kind": "r77a-action-exploration", "status": status,
            "scene": source["id"], "scene_sha256": source_hash,
            "config": {"seeds": list(seeds), "ticks_per_seed": ticks_per_seed,
                       "state_budget": state_budget},
            "coverage": {"zones": [list(c) for c in sorted(all_zones)],
                         "goals": [list(c) for c in sorted(all_goals)],
                         "conditions": sorted(conditions), "actions": sorted(actions)},
            "static_preflight": static, "runs": runs, "failures": failures,
            "runtime_replay_verified": all(r["replay_verified"] for r in runs),
            "release_certified": False,
            "limitations": ["R26 single-scene only, not GameSession or multi-genre",
                            "static softlock witnesses are abstract, not runtime proof",
                            "bounded agent coverage is not exhaustive or human UX/GPU QA"]}
