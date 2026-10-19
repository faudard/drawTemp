"""R34.C — opt-in roguelite run controller owned by the canonical GameSession.

Authoritative authoring data stays in GameProject.extensions. Runtime state and
the deterministic command log belong to GameSession, never to a Qt dialog or
an independent save file. CT, Campaign gold and legacy Player slots are untouched.
"""
from __future__ import annotations

from copy import copy, deepcopy

from .model import RuleError, require

EXTENSION = "org.drawtemp.roguelite"
VERSION = 1
MAX_COMMANDS = 2048
MAX_RUNS = 256


def validate_roguelite_spec(spec, *, content, project):
    """Fail closed on unsupported versions, references and unsolvable prefabs."""
    from drawtemp.sdk.procgen import ProcGenRecipe
    from drawtemp.sdk.procgen_prefabs import generate_with_prefabs, validate_library

    require(type(spec) is dict and set(spec) ==
            {"version", "recipe", "library", "biome", "meta_reward"},
            "Malformed R34 roguelite project extension")
    require(type(spec["version"]) is int and spec["version"] == VERSION,
            "Unsupported R34 roguelite version")
    require(type(spec["meta_reward"]) is int and
            0 <= spec["meta_reward"] <= 1000,
            "R34 meta reward must be an integer in 0..1000")
    require(type(spec["biome"]) is str and bool(spec["biome"]),
            "R34 biome is required")
    recipe = ProcGenRecipe.from_dict(spec["recipe"])
    require(recipe.seed + MAX_RUNS <= (1 << 63) - 1,
            "R34 seed range exceeds deterministic run budget")
    library = validate_library(spec["library"], content=content, project=project)
    generate_with_prefabs(recipe, library, biome=spec["biome"],
                          content=content, project=project)
    return deepcopy(spec)


class RogueliteRun:
    """Replay-verified dungeon state, temporary inventory and durable meta state.

    One run is indexed by a deterministic seed offset. The *only* authoritative
    history is the bounded, validated command sequence; stored snapshots are
    verified against its replay. Successful commands commit atomically.
    """

    def __init__(self, spec, *, content, project):
        from drawtemp.sdk.procgen import ProcGenRecipe

        self.spec = validate_roguelite_spec(spec, content=content, project=project)
        self._content = content
        self._project = project
        self._recipe = ProcGenRecipe.from_dict(spec["recipe"])
        self._commands = []
        self._run_index = 0
        self._meta = {"coins": 0, "wins": 0, "deaths": 0}
        self._new_run()

    def _new_run(self):
        from dataclasses import replace
        from drawtemp.sdk.procgen_prefabs import generate_with_prefabs

        recipe = replace(self._recipe, seed=self._recipe.seed + self._run_index)
        self._layout = generate_with_prefabs(
            recipe, self.spec["library"], biome=self.spec["biome"],
            content=self._content, project=self._project)
        self._rooms = {room["id"]: room for room in self._layout["rooms"]}
        self._position = next(room["id"] for room in self._rooms.values()
                              if room["role"] == "entry")
        self._visited = {self._position}
        self._keys = set(self._rooms[self._position]["keys"])
        self._claimed = set()
        self._loot = 0
        self._status = "active"
        self._checkpoint = None

    def snapshot(self):
        """Detached presentation value; no mutable references escape."""
        return deepcopy({
            "version": VERSION, "run_index": self._run_index,
            "seed": self._recipe.seed + self._run_index,
            "layout_digest": self._layout["digest"],
            "layout": self._layout,
            "position": self._position,
            "visited": sorted(self._visited),
            "keys": sorted(self._keys),
            "claimed": sorted(self._claimed),
            "inventory": {"loot": self._loot},
            "status": self._status,
            "checkpoint": self._checkpoint,
            "meta": self._meta,
        })

    def _transition(self, kind, value=None):
        require(self._status == "active" or kind == "restart",
                "R34 run ended; restart before acting")
        if kind == "move":
            require(type(value) is int and value in self._rooms[self._position]["neighbors"],
                    "R34 move requires an adjacent room")
            room = self._rooms[value]
            edge = next(door for door in self._rooms[self._position]["doors"]
                        if door["to"] == value)
            locked = next((lock for lock in self._layout["locks"]
                           if {lock["a"], lock["b"]} == {self._position, value}), None)
            require(locked is None or locked["key"] in self._keys,
                    "R34 door requires a key")
            # Both ends must match the authored socket kind.
            require(any(door["kind"] == reverse["kind"] and
                        reverse["to"] == self._position
                        for reverse in room["doors"]),
                    "R34 broken door connection")
            self._position = value
            self._visited.add(value)
            self._keys.update(room["keys"])
            if room["role"] == "exit":
                goal = next(item["id"] for item in self._rooms.values()
                            if item["role"] == "goal")
                require(goal in self._visited,
                        "R34 exit requires visiting the goal")
                self._status = "won"
                self._meta["wins"] += 1
                self._meta["coins"] += self.spec["meta_reward"]
        elif kind == "claim":
            require(value is None and self._position not in self._claimed
                    and self._rooms[self._position]["loot"] > 0,
                    "R34 room loot missing or already claimed")
            self._loot += self._rooms[self._position]["loot"]
            self._claimed.add(self._position)
        elif kind == "checkpoint":
            require(value is None, "R34 checkpoint does not take an argument")
            self._checkpoint = {
                "room": self._position, "step": len(self._commands) + 1}
        elif kind == "die":
            require(value is None, "R34 death does not take an argument")
            self._status = "dead"
            self._meta["deaths"] += 1
        elif kind == "restart":
            require(value is None and self._status in ("won", "dead"),
                    "R34 restart needs a completed or dead run")
            require(self._run_index + 1 < MAX_RUNS,
                    "R34 maximum number of runs reached")
            self._run_index += 1
            self._new_run()
        else:
            raise RuleError("Unknown R34 run action")

    def action(self, kind, value=None):
        require(type(kind) is str and kind in
                ("move", "claim", "checkpoint", "die", "restart"),
                "Unknown R34 command")
        require(len(self._commands) < MAX_COMMANDS,
                "R34 command budget exhausted")
        # Candidate owns its own mutable state, but shares the validated,
        # read-only canonical Content and GameProject references.
        candidate = copy(self)
        candidate._commands = list(self._commands)
        candidate._visited = set(self._visited)
        candidate._keys = set(self._keys)
        candidate._claimed = set(self._claimed)
        candidate._meta = dict(self._meta)
        candidate._checkpoint = deepcopy(self._checkpoint)
        # Content/GameProject and the generated layout are treated as read-only
        # throughout actions; avoid expensive and unsafe ownership duplication.
        candidate._transition(kind, value)
        candidate._commands.append({"kind": kind, "value": value})
        self._commands = candidate._commands
        self._run_index = candidate._run_index
        self._layout = candidate._layout
        self._rooms = candidate._rooms
        self._position = candidate._position
        self._visited = candidate._visited
        self._keys = candidate._keys
        self._claimed = candidate._claimed
        self._loot = candidate._loot
        self._status = candidate._status
        self._checkpoint = candidate._checkpoint
        self._meta = candidate._meta
        return self.snapshot()

    def recording(self):
        from .game_session import digest
        data = {"version": VERSION, "kind": "roguelite_run",
                "commands": deepcopy(self._commands), "state": self.snapshot()}
        return {**data, "digest": digest(data)}

    @classmethod
    def from_recording(cls, spec, data, *, content, project):
        """Derive saved run+meta from valid events, rejecting forged snapshots."""
        from .game_session import digest

        require(type(data) is dict and set(data) ==
                {"version", "kind", "commands", "state", "digest"}
                and type(data["version"]) is int and data["version"] == VERSION
                and data["kind"] == "roguelite_run",
                "Malformed R34 recording")
        require(data["digest"] == digest({k: v for k, v in data.items()
                                         if k != "digest"}),
                "R34 recording checksum mismatch")
        commands = data["commands"]
        require(type(commands) is list and len(commands) <= MAX_COMMANDS,
                "R34 invalid command journal length")
        restored = cls(spec, content=content, project=project)
        for cmd in commands:
            require(type(cmd) is dict and set(cmd) == {"kind", "value"},
                    "R34 command log contains an invalid event")
            restored.action(cmd["kind"], cmd["value"])
        require(restored.snapshot() == data["state"],
                "R34 replay disagrees with checkpoint/meta progression")
        return restored
