"""R65.A (opt-in): integer-tick action combat on top of the R26 runtime.

The R26 scene and legacy replay formats are unchanged. R65 stores only
combat-specific transient state; R26 remains authoritative for actors, HP,
movement, inventory, collisions and the tick counter. No render-time input.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

from sporebound.action_runtime import (
    ActionRuntime, ActionError, MAX_TICKS, RADIUS, SCALE, _center,
    _check, _digest, _input, validate_scene,
)
from sporebound.storage import write_json

R65_VERSION = 2
MAX_PROJECTILES = 24


def validate_combat_rules(value):
    """Strict bounded data, never expressions/scripts or arbitrary callbacks."""
    _check(type(value) is dict and set(value) == {"version", "combo", "projectile"}
           and type(value["version"]) is int and value["version"] == 1,
           "Unsupported R65 combat rules")
    combo = value["combo"]
    _check(type(combo) is list and 1 <= len(combo) <= 4, "Invalid combo sequence")
    for move in combo:
        _check(type(move) is dict and set(move) == {
            "windup", "active", "recovery", "range", "damage", "stagger", "burn_ticks"
        }, "Invalid combo move fields")
        for field, low, high in (
            ("windup", 1, 60), ("active", 1, 30), ("recovery", 1, 90),
            ("range", 300, 1800), ("damage", 1, 30),
            ("stagger", 0, 60), ("burn_ticks", 0, 120),
        ):
            _check(type(move[field]) is int and low <= move[field] <= high,
                   "Invalid combo " + field)
    shot = value["projectile"]
    _check(type(shot) is dict and set(shot) == {
        "speed", "ttl", "cooldown", "damage", "stagger", "burn_ticks"
    }, "Invalid projectile fields")
    for field, low, high in (
        ("speed", 100, 1000), ("ttl", 1, 60), ("cooldown", 1, 120),
        ("damage", 1, 30), ("stagger", 0, 60), ("burn_ticks", 0, 120),
    ):
        _check(type(shot[field]) is int and low <= shot[field] <= high,
               "Invalid projectile " + field)
    return deepcopy(value)


def _r65_input(command, tick):
    _check(type(command) is dict and set(command) <= {
        "tick", "dx", "dy", "attack", "dodge", "guard", "interact", "parry", "fire"
    }, "Unknown R65 input")
    base = _input({key: value for key, value in command.items()
                   if key not in ("parry", "fire")}, tick)
    for key in ("parry", "fire"):
        _check(type(command.get(key, False)) is bool, "Invalid " + key + " input")
    return {**base, "parry": command.get("parry", False),
            "fire": command.get("fire", False)}


class ActionCombatR65(ActionRuntime):
    """Optional R65 combat layer; does not change any R26 ActionRuntime users."""

    def __init__(self, scene, rules, *, initial_inventory=None):
        self.rules = validate_combat_rules(rules)
        super().__init__(scene, initial_inventory=initial_inventory)
        self.rules_digest = _digest(self.rules)
        self.combo = {"stage": -1, "phase": "idle", "left": 0,
                      "queued": False, "hit_ids": []}
        self.projectiles = []
        self.next_projectile_id = 1
        self.fire_cooldown = 0
        self.parry_window = 0
        self.parry_cooldown = 0
        self.statuses = {name: {"burn_left": 0} for name in self.enemies}

    def snapshot(self):
        result = super().snapshot()
        result["version"] = R65_VERSION
        result["r65"] = deepcopy({
            "rules_digest": self.rules_digest, "combo": self.combo,
            "projectiles": self.projectiles, "next_projectile_id": self.next_projectile_id,
            "fire_cooldown": self.fire_cooldown, "parry_window": self.parry_window,
            "parry_cooldown": self.parry_cooldown, "statuses": self.statuses,
        })
        return result

    def _hurt_hero(self, damage, attacker, guard):
        if self.parry_window and self.hero["alive"] and self.hero["stamina"] >= 5:
            self.hero["stamina"] -= 5
            self.parry_window = 0
            if attacker in self.enemies and self.enemies[attacker]["hp"] > 0:
                self.enemies[attacker]["stun"] = max(
                    self.enemies[attacker]["stun"], 12)
            self._emit("hero_parry", source=attacker)
            return
        super()._hurt_hero(damage, attacker, guard)

    def _hit_enemy(self, name, damage, stagger, burn_ticks, source):
        enemy = self.enemies[name]
        if enemy["hp"] <= 0:
            return
        enemy["hp"] = max(0, enemy["hp"] - damage)
        enemy["stun"] = max(enemy["stun"], stagger)
        if enemy["hp"] > 0:
            self.statuses[name]["burn_left"] = max(
                self.statuses[name]["burn_left"], burn_ticks)
        self._emit("enemy_hit", enemy=name, damage=damage, source=source)
        if enemy["hp"] == 0:
            enemy["state"] = "dead"
            self.statuses[name]["burn_left"] = 0
            flag = "defeated:" + name
            if not self.flags.get(flag, False):
                self.flags[flag] = True
                self.inventory["coin"] = self.inventory.get("coin", 0) + 1
                self._emit("enemy_dead", enemy=name, reward="coin")

    def _solid_at(self, x, y):
        if not (0 <= x < self.scene["width"] * SCALE and
                0 <= y < self.scene["height"] * SCALE):
            return True
        if (x // SCALE, y // SCALE) in self._walls:
            return True
        for row in self.scene["objects"]:
            if row["kind"] == "door" and not self.objects[row["id"]]["opened"]:
                cx, cy = _center(row["pos"])
                if abs(x - cx) <= SCALE // 2 and abs(y - cy) <= SCALE // 2:
                    return True
        return False

    def _ray_clear(self, start, end):
        dx, dy = end[0] - start[0], end[1] - start[1]
        count = max(1, (max(abs(dx), abs(dy)) + 99) // 100)
        return all(not self._solid_at(start[0] + dx * i // count,
                                      start[1] + dy * i // count)
                   for i in range(1, count + 1))

    def _start_swing(self, index):
        self.combo = {"stage": index, "phase": "windup",
                      "left": self.rules["combo"][index]["windup"],
                      "queued": False, "hit_ids": []}
        self._emit("attack_telegraph", stage=index)

    def _melee_hits(self):
        move = self.rules["combo"][self.combo["stage"]]
        hx, hy = self.hero["pos"]
        fx, fy = self.hero["facing"]
        for name in sorted(self.enemies):
            enemy = self.enemies[name]
            if enemy["hp"] <= 0 or name in self.combo["hit_ids"]:
                continue
            dx, dy = enemy["pos"][0] - hx, enemy["pos"][1] - hy
            if (dx * dx + dy * dy > move["range"] ** 2 or
                    dx * fx + dy * fy <= 0 or
                    abs(dx * fy - dy * fx) > 450 * max(1, abs(fx) + abs(fy)) or
                    not self._ray_clear([hx, hy], enemy["pos"])):
                continue
            self.combo["hit_ids"].append(name)
            self._hit_enemy(name, move["damage"], move["stagger"],
                            move["burn_ticks"], "melee")

    def _advance_swing(self, pressed):
        swing = self.combo
        if swing["phase"] == "idle":
            if pressed and self.hero["alive"] and not self.hero["dodge_left"]:
                self._start_swing(0)
            return
        if swing["phase"] == "recovery" and pressed:
            swing["queued"] = True
        if swing["phase"] == "active" and self.hero["alive"]:
            self._melee_hits()
        swing["left"] -= 1
        if swing["left"] > 0:
            return
        move = self.rules["combo"][swing["stage"]]
        if swing["phase"] == "windup":
            swing["phase"], swing["left"] = "active", move["active"]
            self._emit("attack_active", stage=swing["stage"])
        elif swing["phase"] == "active":
            swing["phase"], swing["left"] = "recovery", move["recovery"]
        else:
            stage = swing["stage"] + 1
            if swing["queued"] and stage < len(self.rules["combo"]) and self.hero["alive"]:
                self._start_swing(stage)
            else:
                self.combo = {"stage": -1, "phase": "idle", "left": 0,
                              "queued": False, "hit_ids": []}

    def _advance_statuses(self):
        for name in sorted(self.enemies):
            left = self.statuses[name]["burn_left"]
            if left <= 0 or self.enemies[name]["hp"] <= 0:
                continue
            if self.tick % 10 == 0:
                self._hit_enemy(name, 1, 0, 0, "burn")
            if self.enemies[name]["hp"] > 0:
                self.statuses[name]["burn_left"] = left - 1

    def _spawn_shot(self):
        if (not self.hero["alive"] or self.hero["dodge_left"] or
                self.fire_cooldown or len(self.projectiles) >= MAX_PROJECTILES):
            return
        fx, fy = self.hero["facing"]
        if not (fx or fy):
            return
        # 707/1000 fixed-point approximation, like R26 diagonal movement.
        vx, vy = ((fx * 707, fy * 707) if fx and fy else (fx * 1000, fy * 1000))
        x, y = self.hero["pos"]
        self.projectiles.append({"id": self.next_projectile_id,
                                 "pos": [x, y], "dir": [vx, vy],
                                 "ttl": self.rules["projectile"]["ttl"]})
        self._emit("projectile_spawn", projectile=self.next_projectile_id)
        self.next_projectile_id += 1
        self.fire_cooldown = self.rules["projectile"]["cooldown"]

    def _advance_projectiles(self):
        shot = self.rules["projectile"]
        survivors = []
        for missile in self.projectiles:
            x, y = missile["pos"]
            vx = missile["dir"][0] * shot["speed"] // 1000
            vy = missile["dir"][1] * shot["speed"] // 1000
            count = max(1, (max(abs(vx), abs(vy)) + 79) // 80)
            hit = False
            for i in range(1, count + 1):
                px, py = x + vx * i // count, y + vy * i // count
                if self._solid_at(px, py):
                    hit = True
                    self._emit("projectile_blocked", projectile=missile["id"])
                    break
                for name in sorted(self.enemies):
                    enemy = self.enemies[name]
                    if enemy["hp"] <= 0:
                        continue
                    dx, dy = enemy["pos"][0] - px, enemy["pos"][1] - py
                    if dx * dx + dy * dy <= RADIUS ** 2:
                        self._hit_enemy(name, shot["damage"], shot["stagger"],
                                        shot["burn_ticks"], "projectile")
                        hit = True
                        break
                if hit:
                    break
            missile["ttl"] -= 1
            if not hit and missile["ttl"] > 0:
                missile["pos"] = [x + vx, y + vy]
                survivors.append(missile)
            elif not hit:
                self._emit("projectile_expired", projectile=missile["id"])
        self.projectiles = survivors

    def step(self, command):
        _check(self.tick < MAX_TICKS, "R65 replay tick budget exceeded")
        frame = _r65_input(command, self.tick + 1)
        # One atomic transaction, no quadratic copy of the command journal.
        original = deepcopy((self.tick, self.hero, self.enemies, self.objects,
                             self.inventory, self.flags, self.last_events,
                             self.combo, self.projectiles, self.next_projectile_id,
                             self.fire_cooldown, self.parry_window,
                             self.parry_cooldown, self.statuses))
        count = len(self.commands)
        try:
            self.fire_cooldown = max(0, self.fire_cooldown - 1)
            self.parry_cooldown = max(0, self.parry_cooldown - 1)
            self.parry_window = max(0, self.parry_window - 1)
            if (frame["parry"] and not frame["dodge"] and
                    self.parry_cooldown == 0 and self.hero["alive"] and
                    self.hero["stamina"] >= 5):
                self.parry_window, self.parry_cooldown = 3, 18
            # R26 owns movement, guard, dodge, enemy AI and interaction.
            native = {key: frame[key] for key in (
                "tick", "dx", "dy", "attack", "dodge", "guard", "interact")}
            native["attack"] = False
            super().step(native)
            self._advance_statuses()
            self._advance_swing(frame["attack"])
            if frame["fire"]:
                self._spawn_shot()
            self._advance_projectiles()
            self.commands[-1] = frame
            return deepcopy(self.last_events)
        except Exception:
            (self.tick, self.hero, self.enemies, self.objects,
             self.inventory, self.flags, self.last_events,
             self.combo, self.projectiles, self.next_projectile_id,
             self.fire_cooldown, self.parry_window,
             self.parry_cooldown, self.statuses) = original
            del self.commands[count:]
            raise

    def recording(self):
        return {"version": R65_VERSION, "scene": deepcopy(self.scene),
                "scene_digest": self.scene_digest, "rules": deepcopy(self.rules),
                "rules_digest": self.rules_digest, "commands": deepcopy(self.commands),
                "initial_inventory": deepcopy(self.initial_inventory),
                "state_digest": self.digest()}

    @classmethod
    def from_recording(cls, recorded, *, expected_scene=None, expected_rules=None):
        _check(type(recorded) is dict and set(recorded) == {
            "version", "scene", "scene_digest", "rules", "rules_digest",
            "commands", "initial_inventory", "state_digest"
        } and type(recorded["version"]) is int and recorded["version"] == R65_VERSION,
               "Unsupported R65 replay format")
        rules = validate_combat_rules(recorded["rules"])
        scene = validate_scene(recorded["scene"])
        _check(type(recorded["scene_digest"]) is str and
               type(recorded["rules_digest"]) is str and
               type(recorded["state_digest"]) is str and
               _digest(scene) == recorded["scene_digest"] and
               _digest(rules) == recorded["rules_digest"],
               "R65 recording checksum mismatch")
        if expected_scene is not None:
            _check(_digest(validate_scene(expected_scene)) == recorded["scene_digest"],
                   "R65 recording scene changed")
        if expected_rules is not None:
            _check(_digest(validate_combat_rules(expected_rules)) == recorded["rules_digest"],
                   "R65 recording rules changed")
        commands = recorded["commands"]
        _check(type(commands) is list and len(commands) <= MAX_TICKS,
               "Invalid R65 replay command budget")
        runner = cls(scene, rules, initial_inventory=recorded["initial_inventory"])
        for command in commands:
            runner.step(command)
        _check(runner.digest() == recorded["state_digest"],
               "R65 replay state diverged")
        return runner

    def save(self, path):
        write_json(path, self.recording())

    @classmethod
    def load(cls, path, *, expected_scene=None, expected_rules=None):
        try:
            recorded = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ActionError("Unable to load R65 checkpoint") from exc
        return cls.from_recording(recorded, expected_scene=expected_scene,
                                  expected_rules=expected_rules)
