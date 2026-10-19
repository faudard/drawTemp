"""R34.A: bounded, deterministic room-graph generation for Creator projects.

The generator is headless and intentionally does not own GameSession, project
persistence, assets, or the Player. Studio/Player can consume detached payloads;
integration with the canonical GameSession/save format is a later R34 lot.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from typing import Any, Mapping


RECIPE_VERSION = 1
ALGORITHM = "room-graph-v1"
MAX_ROOMS = 64
MAX_BUDGET = 256
MAX_BATCH = 500


class ProcGenError(ValueError):
    """Stable code for Studio diagnostics, without partial generated output."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(code: str, message: str):
    raise ProcGenError(code, message)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _int(value: Any, name: str, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        _fail("invalid_recipe", f"{name} must be an integer in [{lower}, {upper}]")
    return value


@dataclass(frozen=True)
class ProcGenRecipe:
    """Versioned, JSON-compatible declarative input (no runtime objects)."""

    seed: int
    rooms: int = 8
    branches: int = 2
    locked_goal: bool = False
    encounter_budget: int = 4
    loot_budget: int = 3
    schema_version: int = RECIPE_VERSION
    algorithm: str = ALGORITHM

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ProcGenRecipe:
        if not isinstance(data, Mapping):
            _fail("invalid_recipe", "recipe must be a mapping")
        allowed = set(cls.__dataclass_fields__)
        if set(data) - allowed or "seed" not in data:
            _fail("invalid_recipe", "unknown recipe field or missing seed")
        try:
            obj = cls(**data)
        except TypeError as exc:
            raise ProcGenError("invalid_recipe", "incorrect recipe fields") from exc
        obj.validate()
        return obj

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.__dataclass_fields__}

    def validate(self) -> None:
        _int(self.schema_version, "schema_version", RECIPE_VERSION, RECIPE_VERSION)
        if self.algorithm != ALGORITHM:
            _fail("unsupported_algorithm", "unrecognized generation algorithm")
        _int(self.seed, "seed", 0, (1 << 63) - 1)
        _int(self.rooms, "rooms", 3, MAX_ROOMS)
        _int(self.branches, "branches", 0, self.rooms - 3)
        _int(self.encounter_budget, "encounter_budget", 0, MAX_BUDGET)
        _int(self.loot_budget, "loot_budget", 0, MAX_BUDGET)
        if type(self.locked_goal) is not bool:
            _fail("invalid_recipe", "locked_goal must be boolean")
        if self.locked_goal and not self.branches:
            _fail("unsatisfiable_recipe", "locked goal requires a key branch")
        # At most sixteen placements of each kind in any non-terminal room.
        if max(self.loot_budget, self.encounter_budget) > (self.rooms - 2) * 16:
            _fail("unsatisfiable_recipe", "placement budget exceeds room capacity")


class _Stream:
    """SHA-256 counter stream: no global RNG or Python random state."""

    def __init__(self, seed: int, purpose: str):
        self.key = _canonical([ALGORITHM, seed, purpose])
        self.counter = 0

    def below(self, limit: int) -> int:
        if limit < 1:
            _fail("invalid_budget", "empty deterministic choice")
        # Rejection sampling avoids modulo bias; 256-bit space is ample.
        max_value = (1 << 256) - ((1 << 256) % limit)
        while True:
            digest = sha256(self.key + self.counter.to_bytes(8, "big")).digest()
            self.counter += 1
            value = int.from_bytes(digest, "big")
            if value < max_value:
                return value % limit


def _path(rooms: list[dict[str, Any]], locks: list[dict[str, Any]]) -> list[int] | None:
    """Explore location, key possession, and goal visit; never infer reachability."""
    lock_edges = {(min(row["a"], row["b"]), max(row["a"], row["b"])): row["key"]
                  for row in locks}
    by_id = {row["id"]: row for row in rooms}
    entry = next(row["id"] for row in rooms if row["role"] == "entry")
    goal = next(row["id"] for row in rooms if row["role"] == "goal")
    finish = next(row["id"] for row in rooms if row["role"] == "exit")
    first = (entry, frozenset(), entry == goal)
    queue = deque([(first, (entry,))])
    visited = {first}
    while queue:
        (position, inventory, found_goal), route = queue.popleft()
        keys = inventory | frozenset(by_id[position]["keys"])
        if position == finish and found_goal:
            return list(route)
        for destination in by_id[position]["neighbors"]:
            required = lock_edges.get((min(position, destination), max(position, destination)))
            if required is not None and required not in keys:
                continue
            nxt = (destination, keys, found_goal or destination == goal)
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, (*route, destination)))
    return None


def _decorate(rooms: list[dict[str, Any]], seed: int, field: str, budget: int) -> None:
    rng = _Stream(seed, field)
    eligible = [row for row in rooms if row["role"] not in ("entry", "exit")]
    for _ in range(budget):
        available = [room for room in eligible if room[field] < 16]
        rooms_index = rng.below(len(available))
        available[rooms_index][field] += 1


def generate(recipe: ProcGenRecipe | Mapping[str, Any]) -> dict[str, Any]:
    """Generate a detached, reproducible dungeon. Never mutates recipe/content.

    The graph is deliberately topology-only: replacing GameProject map/asset
    references or persisting a run must happen via later validated adapters.
    """
    if not isinstance(recipe, ProcGenRecipe):
        recipe = ProcGenRecipe.from_dict(recipe)
    recipe.validate()
    rng = _Stream(recipe.seed, "topology")
    main = recipe.rooms - recipe.branches
    goal, finish = main - 2, main - 1
    rooms = [{"id": i, "role": "normal", "neighbors": [], "keys": [],
              "encounters": 0, "loot": 0} for i in range(recipe.rooms)]
    rooms[0]["role"] = "entry"
    rooms[goal]["role"] = "goal"
    rooms[finish]["role"] = "exit"

    def link(a: int, b: int) -> None:
        rooms[a]["neighbors"].append(b)
        rooms[b]["neighbors"].append(a)

    for i in range(main - 1):
        link(i, i + 1)
    for i in range(main, recipe.rooms):
        # Attach branches to an accessible section, never behind the goal gate.
        candidates = [row["id"] for row in rooms[:goal] if len(row["neighbors"]) < 4]
        if not candidates:
            _fail("unsatisfiable_recipe", "no room capacity for another branch")
        link(candidates[rng.below(len(candidates))], i)
    locks: list[dict[str, Any]] = []
    if recipe.locked_goal:
        key_room = main + rng.below(recipe.branches)
        rooms[key_room]["role"] = "key"
        rooms[key_room]["keys"] = ["goal_key"]
        locks.append({"a": goal - 1, "b": goal, "key": "goal_key"})
    for room in rooms:
        room["neighbors"].sort()
    _decorate(rooms, recipe.seed, "encounters", recipe.encounter_budget)
    _decorate(rooms, recipe.seed, "loot", recipe.loot_budget)
    route = _path(rooms, locks)
    if route is None:
        _fail("unsatisfiable_recipe", "no route from entry through goal to exit")
    content = {"schema_version": RECIPE_VERSION, "algorithm": ALGORITHM,
               "recipe": recipe.to_dict(), "rooms": rooms, "locks": locks,
               "route": route}
    return {**content, "digest": sha256(_canonical(content)).hexdigest()}


def verify(recipe: ProcGenRecipe | Mapping[str, Any], generated: Mapping[str, Any]) -> list[int]:
    """Strict verification against the authoritative deterministic algorithm.

    A SHA digest detects accidental corruption, not malicious tampering. This
    validation is not a signed export or a substitute for asset/license checks.
    """
    if not isinstance(recipe, ProcGenRecipe):
        recipe = ProcGenRecipe.from_dict(recipe)
    expected = generate(recipe)
    if not isinstance(generated, Mapping) or dict(generated) != expected:
        _fail("invalid_generation", "layout, version, seed, or digest does not match recipe")
    return list(expected["route"])


def generate_batch(recipe: ProcGenRecipe | Mapping[str, Any], seeds: list[int]) -> list[dict[str, Any]]:
    """Bounded certification helper; returns full replayable counterexamples."""
    if not isinstance(recipe, ProcGenRecipe):
        recipe = ProcGenRecipe.from_dict(recipe)
    recipe.validate()
    if type(seeds) is not list or not 1 <= len(seeds) <= MAX_BATCH:
        _fail("invalid_budget", f"batch must contain 1..{MAX_BATCH} seeds")
    results = []
    for seed in seeds:
        replacement = replace(recipe, seed=seed)
        replacement.validate()
        results.append(generate(replacement))
    return results
