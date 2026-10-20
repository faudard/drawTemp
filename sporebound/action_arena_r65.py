"""R65.C — opt-in deterministic action arena powered by the R65.A engine.

The existing action runtime owns positions, HP, combat damage, CT-independent
inventory/rewards, and the fixed tick. This capability adds scripted boss phases,
two coordinated flankers, and enemy projectiles without touching R26 v1 or R65 v2
recordings. Boss patterns are the exact R65.B typed authoring data.
"""
from __future__ import annotations

from copy import deepcopy
from math import isqrt
from pathlib import Path
import json

from sporebound.action_combat_r65 import ActionCombatR65
from sporebound.action_combat_catalog_r65 import validate_preset
from sporebound.action_runtime import (
    ActionError, MAX_TICKS, RADIUS, _check, _digest, _id, validate_scene,
)
from sporebound.storage import write_json

ARENA_VERSION = 3
MAX_HOSTILE_SHOTS = 24


def validate_arena(scene, preset, setup):
    scene = validate_scene(scene)
    preset = validate_preset(preset)
    _check(type(setup) is dict and set(setup) == {"boss_id", "flankers"},
           "R65.C arena requires explicit boss and two flankers")
    ids = {enemy["id"] for enemy in scene["enemies"]}
    boss = setup["boss_id"]
    flankers = setup["flankers"]
    _check(_id(boss) and boss in ids and
           type(flankers) is list and len(flankers) == 2 and
           all(_id(name) and name in ids for name in flankers) and
           len({boss, *flankers}) == 3,
           "R65.C requires three distinct authored enemies")
    phases = {1: [], 2: []}
    for row in preset["boss_patterns"]:
        phases[row["phase"]].append(row)
    _check(len(phases[1]) == 1 and len(phases[2]) == 1,
           "R65.C requires exactly one authored pattern per boss phase")
    _check(phases[1][0]["hp_at_or_below"] == 100 and
           1 <= phases[2][0]["hp_at_or_below"] < 100,
           "R65.C phases must start at 100% then use a lower HP threshold")
    return scene, preset, deepcopy(setup)


class ActionArenaR65(ActionCombatR65):
    """One opt-in runtime. Call step() with a complete next-tick command."""

    def __init__(self, scene, preset, setup, *, initial_inventory=None):
        scene, preset, setup = validate_arena(scene, preset, setup)
        self.preset = preset
        self.setup = setup
        self.preset_digest = _digest(preset)
        self.setup_digest = _digest(setup)
        super().__init__(scene, preset["rules"], initial_inventory=initial_inventory)
        self.boss = {"phase": 1, "step": 0, "repeat": 0,
                     "cooldown": 0, "windup": 0, "casting": False,
                     "attacks": 0}
        self.flankers = {
            name: {"windup": 0, "cooldown": 0}
            for name in setup["flankers"]
        }
        self.hostile_shots = []
        self.next_hostile_id = 1

    def snapshot(self):
        # R65.A already detaches all authoritative state.
        view = super().snapshot()
        view["version"] = ARENA_VERSION
        view["arena"] = deepcopy({
            "boss": self.boss, "flankers": self.flankers,
            "projectiles": self.hostile_shots,
            "boss_id": self.setup["boss_id"],
            "flanker_ids": self.setup["flankers"],
            "victory": self.hero["alive"] and all(
                enemy["hp"] <= 0 for enemy in self.enemies.values()),
            "preset_digest": self.preset_digest,
            "setup_digest": self.setup_digest,
        })
        return view

    def _pattern(self):
        return next(row for row in self.preset["boss_patterns"]
                    if row["phase"] == self.boss["phase"])

    def _lead_ticks(self, kind):
        matching = [row["lead_ticks"] for row in self.preset["telegraphs"]
                    if row["kind"] == kind]
        # At least one tick of warning before any authored boss attack.
        return max(1, matching[0] if matching else 6)

    def _boss_action(self, kind):
        boss_id = self.setup["boss_id"]
        actor = self.enemies[boss_id]
        if actor["hp"] <= 0 or not self.hero["alive"]:
            return
        self.boss["attacks"] += 1
        self._emit("boss_action", boss=boss_id,
                   phase=self.boss["phase"], action=kind)
        if kind == "melee":
            dx = self.hero["pos"][0] - actor["pos"][0]
            dy = self.hero["pos"][1] - actor["pos"][1]
            if dx * dx + dy * dy <= 1450 ** 2 and (
                    self._ray_clear(actor["pos"], self.hero["pos"])):
                self._hurt_hero(2 if self.boss["phase"] == 2 else 1,
                                boss_id, False)
        elif kind == "dodge":
            dx = actor["pos"][0] - self.hero["pos"][0]
            dy = actor["pos"][1] - self.hero["pos"][1]
            length = isqrt(dx * dx + dy * dy)
            if length:
                self._move(boss_id, actor, dx * 360 // length,
                           dy * 360 // length)
        elif kind == "projectile":
            if len(self.hostile_shots) >= MAX_HOSTILE_SHOTS:
                self._emit("boss_projectile_limit", boss=boss_id)
                return
            dx = self.hero["pos"][0] - actor["pos"][0]
            dy = self.hero["pos"][1] - actor["pos"][1]
            length = max(1, isqrt(dx * dx + dy * dy))
            speed = self.rules["projectile"]["speed"]
            vx, vy = dx * speed // length, dy * speed // length
            if vx == 0 and vy == 0:
                return
            self.hostile_shots.append({
                "id": self.next_hostile_id, "source": boss_id,
                "pos": list(actor["pos"]), "velocity": [vx, vy],
                "ttl": self.rules["projectile"]["ttl"],
                "damage": 2 if self.boss["phase"] == 2 else 1,
            })
            self._emit("boss_projectile", boss=boss_id,
                       projectile=self.next_hostile_id)
            self.next_hostile_id += 1

    def _advance_boss(self):
        name = self.setup["boss_id"]
        actor = self.enemies[name]
        if actor["hp"] <= 0 or not self.hero["alive"]:
            self.boss["casting"] = False
            self.boss["windup"] = 0
            return
        max_hp = next(spec["hp"] for spec in self.scene["enemies"]
                      if spec["id"] == name)
        threshold = next(row["hp_at_or_below"]
                         for row in self.preset["boss_patterns"]
                         if row["phase"] == 2)
        if self.boss["phase"] == 1 and actor["hp"] * 100 <= max_hp * threshold:
            self.boss.update(phase=2, step=0, repeat=0,
                             cooldown=0, windup=0, casting=False)
            self._emit("boss_phase", boss=name, phase=2)
        if actor["stun"] > 0:
            actor["stun"] -= 1
            return
        pattern = self._pattern()
        row = pattern["steps"][self.boss["step"]]
        if self.boss["cooldown"]:
            self.boss["cooldown"] -= 1
            return
        if not self.boss["casting"]:
            self.boss["casting"] = True
            self.boss["windup"] = self._lead_ticks(row["kind"])
            self._emit("boss_telegraph", boss=name,
                       phase=self.boss["phase"], action=row["kind"],
                       lead_ticks=self.boss["windup"])
            return
        self.boss["windup"] -= 1
        if self.boss["windup"] > 0:
            return
        self._boss_action(row["kind"])
        self.boss["casting"] = False
        self.boss["cooldown"] = row["wait_ticks"]
        self.boss["repeat"] += 1
        if self.boss["repeat"] >= row["repeat"]:
            self.boss["repeat"] = 0
            self.boss["step"] = (self.boss["step"] + 1) % len(pattern["steps"])

    def _flank_target(self, index):
        hx, hy = self.hero["pos"]
        fx, fy = self.hero["facing"]
        # Two enemies use opposite offsets perpendicular to player facing.
        side = -1 if index == 0 else 1
        return (hx + side * (-fy) * 600,
                hy + side * fx * 600)

    def _advance_flankers(self, guard):
        for index, name in enumerate(self.setup["flankers"]):
            actor = self.enemies[name]
            state = self.flankers[name]
            if actor["hp"] <= 0:
                continue
            state["cooldown"] = max(0, state["cooldown"] - 1)
            if actor["stun"] > 0:
                actor["stun"] -= 1
                continue
            if not self.hero["alive"]:
                state["windup"] = 0
                continue
            dx = self.hero["pos"][0] - actor["pos"][0]
            dy = self.hero["pos"][1] - actor["pos"][1]
            dist2 = dx * dx + dy * dy
            if state["windup"]:
                state["windup"] -= 1
                if state["windup"] == 0 and dist2 <= 850 ** 2:
                    actor["state"] = "attack"
                    self._emit("flanker_attack", enemy=name)
                    self._hurt_hero(1, name, guard)
                    state["cooldown"] = 24
                continue
            if dist2 <= 850 ** 2 and state["cooldown"] == 0:
                actor["state"] = "attack"
                state["windup"] = 5
                self._emit("flanker_telegraph", enemy=name, lead_ticks=5)
                continue
            if dist2 <= (6 * 1000) ** 2:
                tx, ty = self._flank_target(index)
                if dist2 < 850 ** 2:
                    # Avoid walking into the hero during the recovery interval.
                    continue
                vx, vy = tx - actor["pos"][0], ty - actor["pos"][1]
                length = isqrt(vx * vx + vy * vy)
                if length > 0:
                    actor["state"] = "flank"
                    actor["facing"] = [
                        1 if vx > 0 else -1 if vx < 0 else 0,
                        1 if vy > 0 else -1 if vy < 0 else 0]
                    self._move(name, actor, vx * min(85, length) // length,
                               vy * min(85, length) // length)

    def _advance_hostile_shots(self):
        survivors = []
        for shot in self.hostile_shots:
            x, y = shot["pos"]
            vx, vy = shot["velocity"]
            count = max(1, (max(abs(vx), abs(vy)) + 79) // 80)
            hit = False
            for part in range(1, count + 1):
                px = x + vx * part // count
                py = y + vy * part // count
                if self._solid_at(px, py):
                    self._emit("boss_projectile_blocked",
                               projectile=shot["id"])
                    hit = True
                    break
                dx = self.hero["pos"][0] - px
                dy = self.hero["pos"][1] - py
                if self.hero["alive"] and dx * dx + dy * dy <= (
                        2 * RADIUS) ** 2:
                    self._hurt_hero(shot["damage"], shot["source"], False)
                    self._emit("boss_projectile_impact",
                               projectile=shot["id"])
                    hit = True
                    break
            shot["ttl"] -= 1
            if not hit and shot["ttl"] > 0:
                shot["pos"] = [x + vx, y + vy]
                survivors.append(shot)
            elif not hit:
                self._emit("boss_projectile_expired", projectile=shot["id"])
        self.hostile_shots = survivors

    def _enemy_ai(self, guard):
        # R26 still owns enemies/HP/movement. R65.C replaces ONLY this
        # explicitly opted-in scene's AI decisions and attack sequencing.
        self._advance_flankers(guard)
        self._advance_boss()

    def step(self, command):
        # Additional state must also roll back if the R65.A transaction fails.
        extra = deepcopy((self.boss, self.flankers,
                          self.hostile_shots, self.next_hostile_id))
        try:
            result = super().step(command)
            self._advance_hostile_shots()
            return deepcopy(self.last_events)
        except Exception:
            self.boss, self.flankers, self.hostile_shots, self.next_hostile_id = extra
            raise

    def recording(self):
        return {"version": ARENA_VERSION,
                "scene": deepcopy(self.scene),
                "scene_digest": self.scene_digest,
                "preset": deepcopy(self.preset),
                "preset_digest": self.preset_digest,
                "setup": deepcopy(self.setup),
                "setup_digest": self.setup_digest,
                "initial_inventory": deepcopy(self.initial_inventory),
                "commands": deepcopy(self.commands),
                "state_digest": self.digest()}

    @classmethod
    def from_recording(cls, recorded, *, expected_scene=None,
                       expected_preset=None, expected_setup=None):
        _check(type(recorded) is dict and set(recorded) == {
            "version", "scene", "scene_digest",
            "preset", "preset_digest", "setup", "setup_digest",
            "initial_inventory", "commands", "state_digest"
        } and type(recorded["version"]) is int and
               recorded["version"] == ARENA_VERSION,
               "Unsupported R65.C checkpoint")
        scene, preset, setup = validate_arena(
            recorded["scene"], recorded["preset"], recorded["setup"])
        _check(type(recorded["scene_digest"]) is str and
               type(recorded["preset_digest"]) is str and
               type(recorded["setup_digest"]) is str and
               type(recorded["state_digest"]) is str and
               _digest(scene) == recorded["scene_digest"] and
               _digest(preset) == recorded["preset_digest"] and
               _digest(setup) == recorded["setup_digest"],
               "R65.C checkpoint input checksum mismatch")
        if expected_scene is not None:
            _check(_digest(validate_scene(expected_scene)) == recorded["scene_digest"],
                   "R65.C checkpoint refers to another scene")
        if expected_preset is not None:
            _check(_digest(validate_preset(expected_preset)) == recorded["preset_digest"],
                   "R65.C checkpoint refers to another preset")
        if expected_setup is not None:
            _, _, checked = validate_arena(scene, preset, expected_setup)
            _check(_digest(checked) == recorded["setup_digest"],
                   "R65.C checkpoint uses another arena layout")
        commands = recorded["commands"]
        _check(type(commands) is list and len(commands) <= MAX_TICKS,
               "Invalid R65.C checkpoint command count")
        runtime = cls(scene, preset, setup,
                      initial_inventory=recorded["initial_inventory"])
        for command in commands:
            runtime.step(command)
        _check(runtime.digest() == recorded["state_digest"],
               "R65.C checkpoint replay diverged")
        return runtime

    def save(self, path):
        write_json(path, self.recording())

    @classmethod
    def load(cls, path, *, expected_scene=None,
             expected_preset=None, expected_setup=None):
        try:
            recorded = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ActionError("Cannot read R65.C checkpoint") from exc
        return cls.from_recording(
            recorded, expected_scene=expected_scene,
            expected_preset=expected_preset, expected_setup=expected_setup)


def arena_demo():
    """Original, self-contained reference; no third-party art or sidecar schema."""
    from sporebound.action_combat_catalog_r65 import starter_preset
    scene = {
        "id": "r65_stone_arena", "width": 11, "height": 9,
        "walls": [[3, 1], [3, 7], [6, 1], [6, 7]],
        "hero": {"pos": [1, 4], "hp": 40},
        "enemies": [
            {"id": "scout_left", "pos": [5, 2], "hp": 8, "patrol": []},
            {"id": "scout_right", "pos": [5, 6], "hp": 8, "patrol": []},
            {"id": "warden", "pos": [8, 4], "hp": 24, "patrol": []},
        ],
        "objects": [],
    }
    preset = starter_preset("r65_stone_arena")
    preset["label"] = "Arène des pierres"
    preset["rules"]["combo"] += [{
        "windup": 3, "active": 3, "recovery": 7, "range": 1300,
        "damage": 4, "stagger": 8, "burn_ticks": 0,
    }]
    preset["rules"]["projectile"].update(
        speed=900, ttl=24, cooldown=10, damage=6, stagger=4, burn_ticks=0)
    preset["telegraphs"].append({
        "cue": "Charge à distance", "kind": "projectile",
        "stage": -1, "lead_ticks": 6})
    preset["boss_patterns"] = [
        {"id": "warden_opening", "phase": 1, "hp_at_or_below": 100,
         "steps": [{"kind": "projectile", "repeat": 2, "wait_ticks": 10},
                   {"kind": "melee", "repeat": 1, "wait_ticks": 8}]},
        {"id": "warden_enraged", "phase": 2, "hp_at_or_below": 50,
         "steps": [{"kind": "projectile", "repeat": 3, "wait_ticks": 5},
                   {"kind": "dodge", "repeat": 1, "wait_ticks": 6}]},
    ]
    setup = {"boss_id": "warden", "flankers": ["scout_left", "scout_right"]}
    validate_arena(scene, preset, setup)
    return scene, preset, setup


__all__ = ["ActionArenaR65", "validate_arena", "arena_demo"]
