"""R40.B.4 opt-in, deterministic side-view boss combat for R32 scenes.

No actor-specific Qt code, alternate game session, RNG, scripts, or new save
format. Only projects that explicitly author a boss receive this capability.
A telegraph -> strike -> recovery loop offers physical dodge/hit windows.
"""
from __future__ import annotations
from copy import deepcopy

from .model import RuleError


def _need(ok, message):
    if not ok:
        raise RuleError("R40 platform boss: " + message)


def _rect(value, width, height):
    return (type(value) is list and len(value) == 4
            and all(type(x) is int for x in value)
            and value[2] > 0 and value[3] > 0
            and value[0] >= 0 and value[1] >= 0
            and value[0] + value[2] <= width
            and value[1] + value[3] <= height)


def _overlap(a, b):
    return (a[0] < b[0] + b[2] and b[0] < a[0] + a[2]
            and a[1] < b[1] + b[3] and b[1] < a[1] + a[3])


def validate_platform_boss(boss, width, height):
    """Versionless opt-in R32 scene field, exact bounded authoring schema."""
    _need(type(boss) is dict and set(boss) == {
        "id", "rect", "attack_rect", "hp", "phase_at",
        "telegraph", "strike", "recover", "hero_hp",
    }, "invalid authored boss fields")
    _need(type(boss["id"]) is str and 1 <= len(boss["id"]) <= 48
          and all(c.isascii() and (c.isalnum() or c in "_-") for c in boss["id"]),
          "invalid boss id")
    _need(_rect(boss["rect"], width, height) and
          _rect(boss["attack_rect"], width, height),
          "invalid boss or attack geometry")
    _need(type(boss["hp"]) is int and 2 <= boss["hp"] <= 20
          and type(boss["phase_at"]) is int
          and 1 <= boss["phase_at"] < boss["hp"]
          and type(boss["hero_hp"]) is int and 1 <= boss["hero_hp"] <= 20,
          "invalid phase threshold or hit points")
    for key in ("telegraph", "strike", "recover"):
        v = boss[key]
        _need(type(v) is list and len(v) == 2
              and all(type(n) is int and 1 <= n <= 120 for n in v),
              "invalid phase duration: " + key)
    return deepcopy(boss)


class PlatformBoss:
    """One two-phase deterministic encounter, stepped inside R32 journal."""

    def __init__(self, spec):
        self.spec = deepcopy(spec)
        self.hp = spec["hp"]
        self.hero_hp = spec["hero_hp"]
        self.phase = 1
        self.window = "telegraph"
        self.remaining = spec["telegraph"][0]
        self.cooldown = 0
        self.invulnerability = 0

    def snapshot(self):
        return {
            "id": self.spec["id"], "hp": self.hp,
            "max_hp": self.spec["hp"], "hero_hp": self.hero_hp,
            "phase": self.phase, "window": self.window,
            "remaining": self.remaining, "cooldown": self.cooldown,
            "invulnerability": self.invulnerability,
            "rect": list(self.spec["rect"]),
            "attack_rect": list(self.spec["attack_rect"]),
            "defeated": self.hp == 0,
            "player_defeated": self.hero_hp == 0,
        }

    def advance(self, hero, *, attack, tick):
        """Inputs come from the authoritative R32 fixed-tick command."""
        events = []
        if self.hp == 0 or self.hero_hp == 0:
            return events
        if self.cooldown:
            self.cooldown -= 1
        if self.invulnerability:
            self.invulnerability -= 1
        phase_idx = self.phase - 1
        if (attack and self.window == "recover" and self.cooldown == 0
                and _overlap(hero, self.spec["rect"])):
            self.hp -= 1
            self.cooldown = 8
            events.append({"kind": "boss_hit", "boss": self.spec["id"],
                           "hp": self.hp, "tick": tick})
            if self.hp == 0:
                self.window = "defeated"
                self.remaining = 0
                events.append({"kind": "boss_defeated", "boss": self.spec["id"],
                               "tick": tick})
                return events
            if self.phase == 1 and self.hp <= self.spec["phase_at"]:
                self.phase = 2
                events.append({"kind": "boss_phase", "boss": self.spec["id"],
                               "phase": 2, "tick": tick})
        self.remaining -= 1
        if self.remaining:
            return events
        if self.window == "telegraph":
            self.window = "strike"
            self.remaining = self.spec["strike"][self.phase - 1]
            if _overlap(hero, self.spec["attack_rect"]) and not self.invulnerability:
                self.hero_hp -= 1
                self.invulnerability = 12
                events.append({"kind": "hero_hit", "boss": self.spec["id"],
                               "hp": self.hero_hp, "tick": tick})
                if self.hero_hp == 0:
                    self.window = "hero_defeated"
                    self.remaining = 0
                    events.append({"kind": "hero_defeated",
                                   "boss": self.spec["id"], "tick": tick})
                    return events
        elif self.window == "strike":
            self.window = "recover"
            self.remaining = self.spec["recover"][self.phase - 1]
        else:
            self.window = "telegraph"
            self.remaining = self.spec["telegraph"][self.phase - 1]
            events.append({"kind": "boss_telegraph", "boss": self.spec["id"],
                           "phase": self.phase, "tick": tick})
        return events


__all__ = ["PlatformBoss", "validate_platform_boss"]
