"""R32.A/B experimental headless side-view physics capability.

Integer coordinates use 1/1000 tile units at 60 logical ticks/second.
This is an opt-in *adapter*, not a replacement for CT, ActionRuntime or
GameSession. Solid geometry is AABB-only in this first increment.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from sporebound.model import RuleError
from sporebound.storage import write_json

TICK_HZ = 60
SCALE = 1000
VERSION = 1
MAX_TICKS = 20000


class PhysicsError(RuleError):
    """Invalid physics content or command; never repair silently."""


def _require(condition, message):
    if not condition:
        raise PhysicsError(message)


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _integer(value, lower, upper):
    return type(value) is int and lower <= value <= upper


def _id(value):
    return (type(value) is str and 0 < len(value) <= 48
            and all(c.isascii() and (c.isalnum() or c in "_-") for c in value))


def _overlap(a, b):
    return (a[0] < b[0] + b[2] and b[0] < a[0] + a[2]
            and a[1] < b[1] + b[3] and b[1] < a[1] + a[3])


def validate_platform_scene(scene):
    """Fail closed on unexpected keys, out-of-bounds shapes and budgets."""
    _require(type(scene) is dict and set(scene) == {
        "id", "width", "height", "gravity", "hero", "colliders"
    }, "Invalid physics scene schema")
    _require(_id(scene["id"]), "Invalid scene identity")
    width, height = scene["width"], scene["height"]
    _require(_integer(width, SCALE * 3, SCALE * 128)
             and _integer(height, SCALE * 3, SCALE * 128), "Invalid world bounds")
    _require(_integer(scene["gravity"], 0, 1000), "Invalid gravity")
    hero = scene["hero"]
    _require(type(hero) is dict and set(hero) == {
        "pos", "size", "speed", "jump", "max_fall", "coyote"
    }, "Invalid platform actor")
    pos, size = hero["pos"], hero["size"]
    _require(type(pos) is list and len(pos) == 2
             and type(size) is list and len(size) == 2
             and all(_integer(v, 0, SCALE * 128) for v in pos)
             and all(_integer(v, 1, SCALE * 4) for v in size)
             and pos[0] + size[0] <= width and pos[1] + size[1] <= height,
             "Actor spawn out of bounds")
    for field, hi in (("speed", SCALE), ("jump", SCALE * 3),
                      ("max_fall", SCALE * 3), ("coyote", 12)):
        _require(_integer(hero[field], 0, hi), "Invalid actor motion: " + field)
    _require(hero["max_fall"] >= scene["gravity"], "Fall cap below gravity")
    rows = scene["colliders"]
    _require(type(rows) is list and len(rows) <= 256, "Too many colliders")
    ids = set()
    actor = [*pos, *size]
    for row in rows:
        _require(type(row) is dict and
                 {"id", "rect", "layer", "mask", "trigger", "one_way"} <= set(row)
                 and set(row) <= {"id", "rect", "layer", "mask", "trigger",
                                  "one_way", "velocity", "travel", "opens", "route"}
                 and (("velocity" in row) == ("travel" in row))
                 and not ("opens" in row and "route" in row),
                 "Invalid collider schema")
        _require(_id(row["id"]) and row["id"] not in ids, "Duplicate or invalid collider")
        ids.add(row["id"])
        rect = row["rect"]
        _require(type(rect) is list and len(rect) == 4
                 and all(_integer(v, 0, SCALE * 128) for v in rect[:2])
                 and all(_integer(v, 1, SCALE * 128) for v in rect[2:])
                 and rect[0] + rect[2] <= width
                 and rect[1] + rect[3] <= height, "Collider out of bounds")
        _require(_integer(row["layer"], 1, 65535)
                 and _integer(row["mask"], 0, 65535)
                 and type(row["trigger"]) is bool
                 and type(row["one_way"]) is bool, "Invalid collision filter")
        _require(not (row["trigger"] and row["one_way"]), "Trigger cannot be one-way")
        if "opens" in row or "route" in row:
            _require(row["trigger"] and not row["one_way"],
                     "Interactive collider must be a trigger")
            _require(_id(row.get("opens", "")) or _id(row.get("route", "")),
                     "Interactive collider needs an explicit target")
        if "velocity" in row:
            travel = row["travel"]
            _require(not row["trigger"] and row["one_way"],
                     "First R32 adapter only moves one-way solid AABBs")
            _require(_integer(row["velocity"], 1, 500)
                     and type(travel) is list and len(travel) == 2
                     and all(_integer(v, 0, width - rect[2]) for v in travel)
                     and travel[0] < travel[1]
                     and travel[0] <= rect[0] <= travel[1],
                     "Invalid moving-platform travel")
        if not row["trigger"] and not row["one_way"] and _overlap(actor, rect):
            _require(False, "Hero overlaps a solid at spawn")
    for row in rows:
        if "opens" in row:
            _require(_id(row["opens"]) and row["opens"] != row["id"]
                     and any(other["id"] == row["opens"]
                             and not other["trigger"] and not other["one_way"]
                             and "velocity" not in other for other in rows),
                     "Switch must reference a static solid collider")
        if "route" in row:
            _require(_id(row["route"]), "Invalid route trigger reference")
    return deepcopy(scene)


class PlatformPhysics:
    """Single deterministic body + authored AABB solids, one-way platforms and triggers.

    UI calls step() per logical tick, not per rendered frame. Only an opt-in
    mode owner may attach this capability; this module never alters CT state.
    """

    def __init__(self, scene, *, initial_disabled=()):
        self.scene = validate_platform_scene(scene)
        self.scene_digest = _hash(self.scene)
        _require(type(initial_disabled) in (tuple, list)
                 and all(type(v) is str for v in initial_disabled)
                 and len(set(initial_disabled)) == len(initial_disabled),
                 "Invalid initial opened door identifiers")
        doors = {r["id"] for r in self.scene["colliders"]
                 if not r["trigger"] and not r["one_way"] and "velocity" not in r}
        openable = {r["opens"] for r in self.scene["colliders"] if "opens" in r}
        _require(set(initial_disabled) <= (doors & openable),
                 "Checkpoint references an unopenable collider")
        self.initial_disabled = tuple(sorted(initial_disabled))
        self.disabled_colliders = set(self.initial_disabled)
        hero = self.scene["hero"]
        x, y = hero["pos"]
        self.tick = 0
        self.actor = {
            "x": x, "y": y, "vx": 0, "vy": 0, "grounded": False,
            "ground_id": None, "coyote_left": 0,
        }
        self.movers = {
            r["id"]: {"x": r["rect"][0], "dir": 1} for r in self.scene["colliders"]
            if "velocity" in r
        }
        self.inside_triggers = []
        self.commands = []
        self.last_events = []
        ground = self._support()
        if ground is not None:
            self.actor["grounded"] = True
            self.actor["ground_id"] = ground
            self.actor["coyote_left"] = hero["coyote"]
        self.inside_triggers = self._triggers()

    def _rect(self):
        h = self.scene["hero"]
        return [self.actor["x"], self.actor["y"], *h["size"]]

    def _colliders(self):
        for row in sorted(self.scene["colliders"], key=lambda r: r["id"]):
            rect = list(row["rect"])
            if row["id"] in self.movers:
                rect[0] = self.movers[row["id"]]["x"]
            yield row, rect

    def _active(self, row):
        # The actor uses layer=1 and mask=65535; both masks must consent.
        return bool((row["layer"] & 65535) and (row["mask"] & 1))

    def _support(self):
        rect = self._rect()
        if rect[1] + rect[3] == self.scene["height"]:
            return "world"
        for row, block in self._colliders():
            if (row["id"] not in self.disabled_colliders and
                    not row["trigger"] and self._active(row)
                    and rect[1] + rect[3] == block[1]
                    and rect[0] < block[0] + block[2]
                    and rect[0] + rect[2] > block[0]):
                return row["id"]
        return None

    def _triggers(self):
        actor = self._rect()
        return [row["id"] for row, rect in self._colliders()
                if row["trigger"] and self._active(row) and _overlap(actor, rect)]

    def _move_platforms(self):
        moved = {}
        for row in self.scene["colliders"]:
            if row["id"] not in self.movers:
                continue
            m = self.movers[row["id"]]
            lo, hi = row["travel"]
            previous = m["x"]
            proposed = previous + m["dir"] * row["velocity"]
            if proposed > hi:
                proposed = hi
                m["dir"] = -1
            elif proposed < lo:
                proposed = lo
                m["dir"] = 1
            elif proposed == hi:
                m["dir"] = -1
            elif proposed == lo:
                m["dir"] = 1
            m["x"] = proposed
            moved[row["id"]] = proposed - previous
        return moved

    def _sweep(self, axis, distance):
        """Swept AABB per-axis; prevents crossing thin blocks at high velocity."""
        if distance == 0:
            return None
        rect = self._rect()
        idx = 0 if axis == "x" else 1
        other = 1 - idx
        edge = self.scene["width"] if idx == 0 else self.scene["height"]
        max_delta = (edge - rect[idx] - rect[idx + 2]) if distance > 0 else -rect[idx]
        delta = min(distance, max_delta) if distance > 0 else max(distance, max_delta)
        hit = "world" if delta != distance else None
        for row, block in self._colliders():
            if row["id"] in self.disabled_colliders or row["trigger"] or not self._active(row):
                continue
            if row["one_way"] and (idx == 0 or distance < 0):
                continue
            if not (rect[other] < block[other] + block[other + 2]
                    and block[other] < rect[other] + rect[other + 2]):
                continue
            near = block[idx] - (rect[idx] + rect[idx + 2])
            far = block[idx] + block[idx + 2] - rect[idx]
            if distance > 0 and 0 <= near <= delta:
                delta, hit = near, row["id"]
            elif distance < 0 and delta <= far <= 0:
                delta, hit = far, row["id"]
        self.actor[axis] += delta
        return hit

    def available_routes(self):
        """Links requiring explicit transition, only while overlapping the trigger."""
        active = set(self.inside_triggers)
        return sorted({row["route"] for row in self.scene["colliders"]
                       if row.get("route") and row["id"] in active})

    def snapshot(self):
        return deepcopy({
            "version": VERSION, "scene": self.scene["id"], "tick": self.tick,
            "tick_hz": TICK_HZ, "actor": self.actor, "movers": self.movers,
            "inside_triggers": self.inside_triggers,
            "disabled_colliders": sorted(self.disabled_colliders),
            "available_routes": self.available_routes(),
        })

    def digest(self):
        return _hash(self.snapshot())

    def step(self, command):
        _require(self.tick < MAX_TICKS, "Physics tick budget exhausted")
        _require(type(command) is dict and set(command) <= {"tick", "move", "jump", "interact"}
                 and type(command.get("tick")) is int
                 and command["tick"] == self.tick + 1, "Expected next logical tick")
        move, jump = command.get("move", 0), command.get("jump", False)
        interact = command.get("interact", False)
        _require(type(move) is int and move in (-1, 0, 1)
                 and type(jump) is bool and type(interact) is bool,
                 "Invalid platform input")
        frame = {"tick": self.tick + 1, "move": move, "jump": jump,
                 "interact": interact}
        # No arbitrary callbacks or external systems during this deterministic step.
        previous = deepcopy((self.tick, self.actor, self.movers,
                             self.inside_triggers, self.disabled_colliders))
        events = []
        try:
            self.tick += 1
            former_support = self.actor["ground_id"] if self.actor["grounded"] else None
            carried = self._move_platforms().get(former_support, 0)
            if carried:
                self._sweep("x", carried)
            self.actor["vx"] = move * self.scene["hero"]["speed"]
            wall = self._sweep("x", self.actor["vx"])
            if wall is not None:
                self.actor["vx"] = 0
                events.append({"kind": "wall", "collider": wall, "tick": self.tick})
            support = self._support()
            if support is not None:
                self.actor["grounded"] = True
                self.actor["ground_id"] = support
                self.actor["coyote_left"] = self.scene["hero"]["coyote"]
                self.actor["vy"] = 0
            elif self.actor["grounded"]:
                self.actor["grounded"] = False
                self.actor["ground_id"] = None
            if jump and (self.actor["grounded"] or self.actor["coyote_left"] > 0):
                self.actor["vy"] = -self.scene["hero"]["jump"]
                self.actor["grounded"] = False
                self.actor["ground_id"] = None
                self.actor["coyote_left"] = 0
                events.append({"kind": "jump", "tick": self.tick})
            if not self.actor["grounded"]:
                if self.actor["coyote_left"] > 0:
                    self.actor["coyote_left"] -= 1
                self.actor["vy"] = min(self.scene["hero"]["max_fall"],
                                       self.actor["vy"] + self.scene["gravity"])
                hit = self._sweep("y", self.actor["vy"])
                if hit is not None:
                    if self.actor["vy"] > 0:
                        self.actor["grounded"] = True
                        self.actor["ground_id"] = hit
                        self.actor["coyote_left"] = self.scene["hero"]["coyote"]
                        events.append({"kind": "land", "collider": hit,
                                       "tick": self.tick})
                    else:
                        events.append({"kind": "ceiling", "collider": hit,
                                       "tick": self.tick})
                    self.actor["vy"] = 0
            current = self._triggers()
            for name in sorted(set(current) - set(self.inside_triggers)):
                events.append({"kind": "trigger_enter", "collider": name, "tick": self.tick})
            for name in sorted(set(self.inside_triggers) - set(current)):
                events.append({"kind": "trigger_exit", "collider": name, "tick": self.tick})
            self.inside_triggers = current
            if interact:
                for row in sorted(self.scene["colliders"], key=lambda r: r["id"]):
                    target = row.get("opens")
                    if (target and row["id"] in current
                            and target not in self.disabled_colliders):
                        self.disabled_colliders.add(target)
                        events.append({"kind": "door_open", "collider": target,
                                       "switch": row["id"], "tick": self.tick})
            self.commands.append(frame)
            self.last_events = deepcopy(events)
            return deepcopy(events)
        except Exception:
            (self.tick, self.actor, self.movers,
             self.inside_triggers, self.disabled_colliders) = previous
            raise

    def recording(self):
        body = {"version": VERSION, "scene": deepcopy(self.scene),
                "commands": deepcopy(self.commands), "state_digest": self.digest()}
        if self.initial_disabled:
            body["initial_disabled"] = list(self.initial_disabled)
        return {**body, "digest": _hash(body)}

    @classmethod
    def from_recording(cls, raw, *, expected_scene=None):
        _require(type(raw) is dict and
                 set(raw) in ({"version", "scene", "commands", "state_digest", "digest"},
                              {"version", "scene", "commands", "state_digest",
                               "digest", "initial_disabled"})
                 and type(raw["version"]) is int and raw["version"] == VERSION,
                "Unsupported physics recording")
        _require(type(raw["digest"]) is str
                 and _hash({k: v for k, v in raw.items() if k != "digest"})
                 == raw["digest"], "Physics checkpoint digest mismatch")
        game = cls(raw["scene"], initial_disabled=raw.get("initial_disabled", ()))
        if expected_scene is not None:
            _require(game.scene_digest == _hash(validate_platform_scene(expected_scene)),
                     "Physics authored scene changed")
        commands = raw["commands"]
        _require(type(commands) is list and len(commands) <= MAX_TICKS,
                 "Physics replay exceeds budget")
        for command in commands:
            game.step(command)
        _require(game.digest() == raw["state_digest"],
                 "Physics state does not match recorded inputs")
        return game

    def save(self, path):
        write_json(path, self.recording())
        return Path(path)

    @classmethod
    def load(cls, path, *, expected_scene=None):
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PhysicsError("Invalid physics checkpoint") from exc
        return cls.from_recording(raw, expected_scene=expected_scene)


__all__ = ["PlatformPhysics", "PhysicsError", "validate_platform_scene",
           "SCALE", "TICK_HZ", "VERSION"]
