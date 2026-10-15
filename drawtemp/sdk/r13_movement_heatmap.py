"""R13.8 replay movement heatmap derived from actual Battle command frames.

This records observed actor anchor positions at initial state and after each
canonical command. It does NOT infer a path between two recorded coordinates
and never counts an idle actor as a new visit on every unrelated command.
"""
from __future__ import annotations

from collections import Counter

from sporebound.model import require

SCHEMA = 1
MAX_STEPS = 5000
MAX_ENTRIES = 100000
MAX_UNITS_PER_FRAME = 512


def _actor(row, width, height):
    require(type(row) is dict and type(row.get("id")) is str and row["id"]
            and type(row.get("team")) is str and row["team"]
            and type(row.get("alive")) is bool
            and type(row.get("level")) is int and 0 <= row["level"] <= 99
            and type(row.get("pos")) in (list, tuple)
            and len(row["pos"]) == 2
            and all(type(v) is int for v in row["pos"])
            and 0 <= row["pos"][0] < width
            and 0 <= row["pos"][1] < height,
            "Invalid replay actor coordinates / level / team")
    return (row["id"], row["team"], row["level"], list(row["pos"]), row["alive"])


def build_movement_heatmap(trace):
    """Derive entry counts and observed transitions from verified replay.

    Preserves floor identity and teams, including newly appearing units.
    Output visit count includes a separate initial/spawn entry; movement
    counts include only changed anchor cell or floor. Each transition carries
    the canonical command index so selecting a hot cell can seek the replay.
    """
    require(type(trace) is dict and trace.get("kind") == "battle_diagnostics"
            and trace.get("replay_verified") is True
            and type(trace.get("mission")) is str
            and type(trace.get("seed")) is int
            and type(trace.get("digest")) is str
            and type(trace.get("steps")) is list
            and len(trace["steps"]) <= MAX_STEPS
            and type(trace.get("initial")) is dict
            and type(trace.get("board")) is dict,
            "A replay-verified canonical trace is required")
    board = trace["board"]
    width, height = board.get("width"), board.get("height")
    require(type(width) is int and type(height) is int
            and 1 <= width <= 128 and 1 <= height <= 128,
            "Invalid bounded heatmap dimensions")
    transitions = []
    cells = Counter()
    initial_cells = Counter()
    movements = Counter()
    seen_teams = {}
    seen_levels = set()

    def _frame(frame, step, previous, tick):
        require(type(frame) is dict and type(frame.get("units")) is list
                and len(frame["units"]) <= MAX_UNITS_PER_FRAME,
                "Invalid actor frame or actor budget")
        next_state = {}
        for row in frame["units"]:
            uid, team, level, cell, alive = _actor(row, width, height)
            require(uid not in next_state and
                    (uid not in seen_teams or seen_teams[uid] == team),
                    "Duplicate actor ID or changed replay team")
            seen_teams[uid] = team
            next_state[uid] = (team, level, cell, alive)
            if not alive:
                continue
            before = previous.get(uid)
            if before is None or not before[3]:
                kind = "initial" if step == 0 else "spawn"
            elif before[1] != level or before[2] != cell:
                kind = "move"
            else:
                continue
            key = (team, uid, level, cell[0], cell[1])
            cells[key] += 1
            seen_levels.add(level)
            if kind == "move":
                movements[key] += 1
            else:
                initial_cells[key] += 1
            transitions.append({
                "step": step, "tick": tick, "unit": uid, "team": team,
                "level": level, "cell": list(cell), "kind": kind,
                "from_level": before[1] if before else None,
                "from_cell": list(before[2]) if before else None,
            })
            require(len(transitions) <= MAX_ENTRIES,
                    "Replay movement memory budget exceeded")
        return next_state

    initial = trace["initial"]
    require(type(initial.get("tick")) is int,
            "Invalid initial replay tick")
    previous = _frame(initial, 0, {}, initial["tick"])
    for index, step in enumerate(trace["steps"], 1):
        require(type(step) is dict and step.get("index") == index
                and type(step.get("after")) is dict
                and type(step["after"].get("tick")) is int,
                "Unordered / malformed replay command")
        previous = _frame(step["after"], index, previous,
                          step["after"]["tick"])
    rows = [
        {"team": team, "unit": unit, "level": level, "cell": [x, y],
         "visits": count, "initial_or_spawn": initial_cells[key],
         "movements": movements[key]}
        for key, count in sorted(cells.items())
        for team, unit, level, x, y in [key]
    ]
    return {
        "kind": "r13_movement_heatmap", "schema": SCHEMA,
        "mission": trace["mission"], "seed": trace["seed"],
        "digest": trace["digest"], "replay_verified": True,
        "width": width, "height": height, "commands": len(trace["steps"]),
        "levels": sorted(seen_levels),
        "teams": sorted(set(seen_teams.values())),
        "units": [{"id": uid, "team": team}
                  for uid, team in sorted(seen_teams.items())],
        "entries": transitions, "cells": rows,
        "limits": {"steps": MAX_STEPS, "entries": MAX_ENTRIES,
                   "units_per_frame": MAX_UNITS_PER_FRAME},
        "note": (
            "Heatmap of observed actor anchor arrivals, including initial/"
            "spawn separately; no interpolation, pathfinding or multi-cell"
            " footprint reconstruction. Floors remain distinct."),
    }
