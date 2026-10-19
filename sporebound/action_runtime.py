"""R26 action-adventure capability: deterministic, headless 60 Hz scene simulation.

Experimental until the R25 scene/profile router can host this capability. It
does not replace GameSession, the tactical Battle, or their save formats.
Coordinates and velocities use integer 1/1000-tile units; render frames are
never inputs to gameplay.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from math import isqrt
from pathlib import Path
import json

from sporebound.model import RuleError, require
from sporebound.storage import write_json

SCALE = 1000
TICK_HZ = 60
RADIUS = 240
MAX_TICKS = 20000
VERSION = 1


class ActionError(RuleError):
    """Invalid authored scene, input, or replay; never silently repair it."""


def _check(condition, message):
    if not condition:
        raise ActionError(message)


def _digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(raw.encode("utf-8")).hexdigest()


def _id(value):
    return (type(value) is str and 0 < len(value) <= 48
            and all(c.isascii() and (c.isalnum() or c in "_-") for c in value))


def _cell(value, width, height, walls):
    return (type(value) in (list, tuple) and len(value) == 2
            and all(type(n) is int for n in value)
            and 0 <= value[0] < width and 0 <= value[1] < height
            and tuple(value) not in walls)


def _center(cell):
    return [cell[0] * SCALE + SCALE // 2, cell[1] * SCALE + SCALE // 2]


def validate_scene(scene):
    """Validate only explicitly supported R26 geometry and authoring data."""
    _check(type(scene) is dict and set(scene) == {
        "id", "width", "height", "walls", "hero", "enemies", "objects"
    }, "Unknown or missing action-scene fields")
    _check(_id(scene["id"]), "Invalid scene ID")
    w, h = scene["width"], scene["height"]
    _check(type(w) is int and type(h) is int and 3 <= w <= 128 and 3 <= h <= 128,
           "Invalid scene dimensions")
    walls = scene["walls"]
    _check(type(walls) is list and len(walls) <= w * h, "Invalid walls")
    _check(all(type(p) is list and len(p) == 2 and
               all(type(n) is int and 0 <= n < edge for n, edge in zip(p, (w, h)))
               for p in walls), "Invalid wall coordinates")
    solid = {tuple(p) for p in walls}
    _check(len(solid) == len(walls), "Duplicate wall")
    _check(type(scene["hero"]) is dict and set(scene["hero"]) == {"pos", "hp"}
           and _cell(scene["hero"]["pos"], w, h, solid)
           and type(scene["hero"]["hp"]) is int and 1 <= scene["hero"]["hp"] <= 100,
           "Invalid hero")
    _check(type(scene["enemies"]) is list and len(scene["enemies"]) <= 32,
           "Invalid enemy list")
    _check(type(scene["objects"]) is list and len(scene["objects"]) <= 64,
           "Invalid object list")
    taken = {tuple(scene["hero"]["pos"])}
    ids = set()
    for enemy in scene["enemies"]:
        _check(type(enemy) is dict and set(enemy) == {"id", "pos", "hp", "patrol"}
               and _id(enemy["id"]) and enemy["id"] not in ids
               and _cell(enemy["pos"], w, h, solid)
               and type(enemy["hp"]) is int and 1 <= enemy["hp"] <= 30
               and type(enemy["patrol"]) is list and len(enemy["patrol"]) <= 16
               and all(_cell(p, w, h, solid) for p in enemy["patrol"]),
               "Invalid enemy")
        _check(tuple(enemy["pos"]) not in taken, "Overlapping actor spawn")
        taken.add(tuple(enemy["pos"]))
        ids.add(enemy["id"])
    for obj in scene["objects"]:
        _check(type(obj) is dict and set(obj) == {
            "id", "kind", "pos", "item", "requires"
        } and _id(obj["id"]) and obj["id"] not in ids
            and obj["kind"] in ("chest", "door", "sign")
            and _cell(obj["pos"], w, h, solid)
            and (obj["item"] == "" or _id(obj["item"]))
            and (obj["requires"] == "" or _id(obj["requires"])),
            "Invalid interaction object")
        if obj["kind"] == "chest":
            _check(bool(obj["item"]), "A chest must contain an item")
        ids.add(obj["id"])
    return deepcopy(scene)


def _input(command, tick):
    _check(type(command) is dict and set(command) <= {
        "tick", "dx", "dy", "attack", "dodge", "guard", "interact"
    } and command.get("tick") == tick and type(command.get("tick")) is int,
           "Expected the next integer simulation tick")
    dx, dy = command.get("dx", 0), command.get("dy", 0)
    _check(type(dx) is int and type(dy) is int and
           dx in (-1, 0, 1) and dy in (-1, 0, 1), "Input direction must be -1, 0 or 1")
    for name in ("attack", "dodge", "guard"):
        _check(type(command.get(name, False)) is bool, "Invalid " + name + " input")
    interact = command.get("interact", "")
    _check(interact == "" or _id(interact), "Invalid interaction ID")
    return {"tick": tick, "dx": dx, "dy": dy,
            "attack": command.get("attack", False),
            "dodge": command.get("dodge", False),
            "guard": command.get("guard", False),
            "interact": interact}


class ActionRuntime:
    """An opt-in R26 rules capability. A SceneRouter may own one per scene.

    A command describes exactly one logical tick, including an idle tick.
    Callers may draw zero, one or many frames between step() calls.
    """

    def __init__(self, scene):
        self.scene = validate_scene(scene)
        self.scene_digest = _digest(self.scene)
        self._walls = frozenset(tuple(cell) for cell in self.scene["walls"])
        self._enemy_specs = {row["id"]: row for row in self.scene["enemies"]}
        self._object_specs = {row["id"]: row for row in self.scene["objects"]}
        self.tick = 0
        self.hero = {
            "pos": _center(self.scene["hero"]["pos"]), "hp": self.scene["hero"]["hp"],
            "max_hp": self.scene["hero"]["hp"], "facing": [0, 1],
            "stamina": 100, "attack_cd": 0, "dodge_cd": 0,
            "dodge_left": 0, "invulnerable": 0, "alive": True
        }
        self.enemies = {
            row["id"]: {"pos": _center(row["pos"]), "home": _center(row["pos"]),
                        "hp": row["hp"], "facing": [0, 1], "state": "patrol",
                        "attack_cd": 0, "stun": 0, "patrol_index": 0}
            for row in self.scene["enemies"]
        }
        self.objects = {row["id"]: {"opened": False} for row in self.scene["objects"]}
        self.inventory = {}
        self.flags = {}
        self.commands = []
        self.last_events = []

    def snapshot(self):
        return deepcopy({
            "version": VERSION, "scene": self.scene["id"], "tick": self.tick,
            "tick_hz": TICK_HZ, "hero": self.hero, "enemies": self.enemies,
            "objects": self.objects, "inventory": self.inventory, "flags": self.flags,
        })

    def digest(self):
        return _digest(self.snapshot())

    def _emit(self, kind, **fields):
        self.last_events.append({"tick": self.tick, "kind": kind, **fields})

    def _walkable(self, actor_id, x, y):
        w, h = self.scene["width"] * SCALE, self.scene["height"] * SCALE
        if x < RADIUS or y < RADIUS or x > w - RADIUS or y > h - RADIUS:
            return False
        for tx in range((x - RADIUS) // SCALE, (x + RADIUS) // SCALE + 1):
            for ty in range((y - RADIUS) // SCALE, (y + RADIUS) // SCALE + 1):
                if (tx, ty) in self._walls:
                    return False
        # A closed door occupies its authored tile until an explicit interaction.
        for obj in self.scene["objects"]:
            if obj["kind"] != "door" or self.objects[obj["id"]]["opened"]:
                continue
            cx, cy = _center(obj["pos"])
            if abs(x - cx) < SCALE // 2 + RADIUS and abs(y - cy) < SCALE // 2 + RADIUS:
                return False
        # Enemies and hero are dynamic obstacles even without a physics engine.
        others = [("hero", self.hero)] + list(self.enemies.items())
        for name, other in others:
            if name == actor_id or (name == "hero" and not self.hero["alive"]) or (
                    name != "hero" and other["hp"] <= 0):
                continue
            dx, dy = x - other["pos"][0], y - other["pos"][1]
            if dx * dx + dy * dy < (2 * RADIUS) ** 2:
                return False
        return True

    def _move(self, actor_id, actor, vx, vy):
        x, y = actor["pos"]
        if vx and self._walkable(actor_id, x + vx, y):
            x += vx
        if vy and self._walkable(actor_id, x, y + vy):
            y += vy
        actor["pos"] = [x, y]

    def _hurt_hero(self, damage, attacker, guard):
        hero = self.hero
        if not hero["alive"] or hero["invulnerable"]:
            return
        if guard and hero["stamina"] >= 10:
            hero["stamina"] -= 10
            damage = max(0, damage - 1)
            self._emit("guard", source=attacker)
        if damage:
            hero["hp"] = max(0, hero["hp"] - damage)
            hero["invulnerable"] = 18
            self._emit("hero_hit", source=attacker, damage=damage)
            if hero["hp"] == 0:
                hero["alive"] = False
                self._emit("hero_dead")

    def _attack(self):
        hero = self.hero
        if hero["attack_cd"] or not hero["alive"] or hero["dodge_left"]:
            return
        hero["attack_cd"] = 12
        facing = hero["facing"]
        targets = []
        for name, enemy in self.enemies.items():
            if enemy["hp"] <= 0:
                continue
            dx = enemy["pos"][0] - hero["pos"][0]
            dy = enemy["pos"][1] - hero["pos"][1]
            distance = dx * dx + dy * dy
            if distance <= 1250 ** 2 and dx * facing[0] + dy * facing[1] > 0:
                targets.append((distance, name))
        self._emit("hero_attack")
        if targets:
            _, name = min(targets)
            enemy = self.enemies[name]
            enemy["hp"] = max(0, enemy["hp"] - 1)
            enemy["stun"] = 4
            self._emit("enemy_hit", enemy=name, damage=1)
            if enemy["hp"] == 0:
                enemy["state"] = "dead"
                flag = "defeated:" + name
                if not self.flags.get(flag, False):
                    self.flags[flag] = True
                    self.inventory["coin"] = self.inventory.get("coin", 0) + 1
                    self._emit("enemy_dead", enemy=name, reward="coin")

    def _interact(self, object_id):
        row = self._object_specs.get(object_id)
        _check(row is not None, "Unknown interaction object")
        dx = self.hero["pos"][0] - _center(row["pos"])[0]
        dy = self.hero["pos"][1] - _center(row["pos"])[1]
        _check(dx * dx + dy * dy <= 1600 ** 2, "Interaction is out of range")
        obj = self.objects[object_id]
        if obj["opened"]:
            return
        if row["requires"] and self.inventory.get(row["requires"], 0) < 1:
            self._emit("interaction_locked", object=object_id)
            return
        if row["kind"] == "chest":
            self.inventory[row["item"]] = self.inventory.get(row["item"], 0) + 1
        elif row["kind"] == "door" and row["requires"]:
            self.inventory[row["requires"]] -= 1
        if row["kind"] != "sign":
            obj["opened"] = True
            self.flags["opened:" + object_id] = True
        self._emit("interaction", object=object_id, kind_name=row["kind"])

    def _enemy_ai(self, guard):
        hero = self.hero
        for name in sorted(self.enemies):
            enemy = self.enemies[name]
            if enemy["hp"] <= 0:
                continue
            enemy["attack_cd"] = max(0, enemy["attack_cd"] - 1)
            if enemy["stun"]:
                enemy["stun"] -= 1
                continue
            dx = hero["pos"][0] - enemy["pos"][0]
            dy = hero["pos"][1] - enemy["pos"][1]
            dist = dx * dx + dy * dy
            home_dx = enemy["home"][0] - enemy["pos"][0]
            home_dy = enemy["home"][1] - enemy["pos"][1]
            if hero["alive"] and dist <= (4 * SCALE) ** 2:
                enemy["state"] = "chase"
                if dist <= 800 ** 2:
                    enemy["state"] = "attack"
                    if enemy["attack_cd"] == 0:
                        enemy["attack_cd"] = 24
                        self._emit("enemy_attack", enemy=name)
                        self._hurt_hero(1, name, guard)
                    continue
                tx, ty = hero["pos"]
            elif (enemy["state"] in ("chase", "attack", "return")
                  and home_dx * home_dx + home_dy * home_dy > 120 ** 2):
                enemy["state"] = "return"
                tx, ty = enemy["home"]
            else:
                enemy["state"] = "patrol"
                route = self._enemy_specs[name]["patrol"]
                if not route:
                    continue
                point = _center(route[enemy["patrol_index"]])
                if (enemy["pos"][0] - point[0]) ** 2 + (
                        enemy["pos"][1] - point[1]) ** 2 <= 120 ** 2:
                    enemy["patrol_index"] = (enemy["patrol_index"] + 1) % len(route)
                    point = _center(route[enemy["patrol_index"]])
                tx, ty = point
            dx, dy = tx - enemy["pos"][0], ty - enemy["pos"][1]
            length = isqrt(dx * dx + dy * dy)
            if length:
                vx = dx * min(85, length) // length
                vy = dy * min(85, length) // length
                enemy["facing"] = [1 if dx > 0 else -1 if dx < 0 else 0,
                                   1 if dy > 0 else -1 if dy < 0 else 0]
                self._move(name, enemy, vx, vy)

    def step(self, command):
        _check(self.tick < MAX_TICKS, "Action replay tick budget exceeded")
        frame = _input(command, self.tick + 1)  # Fail before mutating any state.
        # Keep rollback bounded: copying the entire input journal each frame
        # would make a long-running 60 Hz session quadratic in elapsed ticks.
        old = deepcopy((self.tick, self.hero, self.enemies, self.objects,
                        self.inventory, self.flags, self.last_events))
        old_command_count = len(self.commands)
        try:
            self.tick += 1
            self.last_events = []
            hero = self.hero
            for name in ("attack_cd", "dodge_cd", "invulnerable"):
                hero[name] = max(0, hero[name] - 1)
            hero["dodge_left"] = max(0, hero["dodge_left"] - 1)
            if hero["alive"]:
                hero["stamina"] = min(100, hero["stamina"] + 1)
                if frame["dx"] or frame["dy"]:
                    hero["facing"] = [frame["dx"], frame["dy"]]
                if (frame["dodge"] and not hero["dodge_cd"]
                        and hero["stamina"] >= 25):
                    hero["dodge_left"] = 6
                    hero["dodge_cd"] = 16
                    hero["invulnerable"] = max(6, hero["invulnerable"])
                    hero["stamina"] -= 25
                    self._emit("hero_dodge")
                speed = 300 if hero["dodge_left"] else 160
                vx = speed * frame["dx"]
                vy = speed * frame["dy"]
                if vx and vy:
                    vx = vx * 707 // 1000
                    vy = vy * 707 // 1000
                self._move("hero", hero, vx, vy)
                if frame["attack"]:
                    self._attack()
                if frame["interact"]:
                    self._interact(frame["interact"])
            self._enemy_ai(frame["guard"] and hero["alive"])
            self.commands.append(frame)
            return deepcopy(self.last_events)
        except Exception:
            (self.tick, self.hero, self.enemies, self.objects, self.inventory,
             self.flags, self.last_events) = old
            del self.commands[old_command_count:]
            raise

    def recording(self):
        return {"version": VERSION, "scene": deepcopy(self.scene),
                "scene_digest": self.scene_digest, "commands": deepcopy(self.commands),
                "state_digest": self.digest()}

    @classmethod
    def from_recording(cls, recorded, *, expected_scene=None):
        _check(type(recorded) is dict and set(recorded) == {
            "version", "scene", "scene_digest", "commands", "state_digest"
        } and type(recorded["version"]) is int and recorded["version"] == VERSION,
               "Unsupported action replay format")
        _check(type(recorded["scene_digest"]) is str and
               type(recorded["state_digest"]) is str, "Invalid replay digest")
        if expected_scene is not None:
            _check(_digest(validate_scene(expected_scene)) == recorded["scene_digest"],
                   "Action replay belongs to different scene/rules")
        runner = cls(recorded["scene"])
        _check(runner.scene_digest == recorded["scene_digest"],
               "Action scene checksum mismatch")
        commands = recorded["commands"]
        _check(type(commands) is list and len(commands) <= MAX_TICKS,
               "Invalid action replay command budget")
        for command in commands:
            runner.step(command)
        _check(runner.digest() == recorded["state_digest"], "Action replay state diverged")
        return runner

    def save(self, path):
        write_json(path, self.recording())

    @classmethod
    def load(cls, path, *, expected_scene=None):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ActionError("Unable to load action checkpoint") from exc
        return cls.from_recording(data, expected_scene=expected_scene)
