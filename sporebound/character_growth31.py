"""Opt-in, bounded character individuality and persistent campaign effects.

The legacy hero/job XP contract is unchanged unless a campaign explicitly chooses
the contribution policy. Combat stats are derived during Campaign.prepare.
"""
from __future__ import annotations

from .model import Unit, require


ORIGINS = {
    "commoner": {},
    "peasant": {"move": 1},
    "noble": {"defense": 1, "max_mp": 2},
    "soldier": {"attack": 1},
    "artisan": {"weapon_power": 1},
}
TRAITS = {
    "steadfast": {"defense": 2, "speed": -1},
    "nimble": {"move": 1, "defense": -1},
    "reckless": {"attack": 2, "defense": -2},
    "careful": {"defense": 1, "attack": -1},
    "resilient": {"max_hp": 6},
}
WOUNDS = {
    "arm_injury": {"attack": -2},
    "leg_injury": {"move": -1},
    "lasting_scar": {"speed": -1},
}
MORALE = {
    "steady": {},
    "shaken": {"attack": -1},
    "wavering": {"attack": -2, "speed": -1},
    "routing": {"attack": -3, "speed": -2},
}
WEAPONS = {"melee", "spear", "ranged", "focus", "unarmed"}


def validate_profile(hero, content=None):
    require(hero.origin in ORIGINS, "Unknown origin")
    require(isinstance(hero.traits, list) and len(hero.traits) <= 2
            and len(hero.traits) == len(set(hero.traits))
            and all(trait in TRAITS for trait in hero.traits),
            "Invalid hero traits")
    require(hero.morale in MORALE, "Invalid morale")
    require(isinstance(hero.wounds, list) and len(hero.wounds) <= 2
            and len(hero.wounds) == len(set(hero.wounds))
            and all(w in WOUNDS for w in hero.wounds), "Invalid wounds")
    require(isinstance(hero.secondary_job, str), "Invalid secondary job")
    if hero.secondary_job:
        require(content is None or hero.secondary_job in content.jobs,
                "Unknown secondary job")
        require(hero.job_xp.get(hero.secondary_job, 0) >= 50,
                "Secondary job requires class training")
        require(hero.secondary_job != hero.job, "Secondary job must differ from primary")
    require(isinstance(hero.weapon_mastery, dict)
            and all(k in WEAPONS and type(v) is int and 0 <= v <= 5
                    for k, v in hero.weapon_mastery.items()), "Invalid weapon mastery")


def apply_profile(content, hero, unit):
    validate_profile(hero, content)
    for family in (ORIGINS[hero.origin], *[TRAITS[t] for t in hero.traits],
                   *[WOUNDS[w] for w in hero.wounds], MORALE[hero.morale]):
        for key, bonus in family.items():
            setattr(unit, key, max(1 if key in {"max_hp", "speed", "weapon_power"} else 0,
                                   getattr(unit, key) + bonus))
    unit.weapon_power += min(3, hero.weapon_mastery.get(unit.weapon, 0))
    if hero.secondary_job:
        spec = content.jobs[hero.secondary_job]
        extras = [skill for skill, level in sorted(spec.get("skills", {}).items())
                  if hero.job_level(hero.secondary_job) >= level]
        for skill in extras[:2]:
            if skill not in unit.skills:
                unit.skills.append(skill)


def contribution(battle, unit_id):
    """Capped first-clear rewards: commands matter, repeated farming does not."""
    actions = sum(event.get("kind") in {"skill", "item", "tactic", "interact",
                                       "prepared_attack", "revive"}
                  and event.get("unit") == unit_id for event in battle.events)
    return {"xp": 75 + min(50, 10 * actions),
            "job_xp": 35 + min(30, 6 * actions),
            "actions": min(actions, 5)}


def apply_battle_history(hero, unit, result, policy):
    if result == "defeat":
        hero.morale = "wavering" if hero.morale == "shaken" else "shaken"
    elif unit.alive:
        hero.morale = "steady"
    if (policy != "off" and unit.hp <= max(1, unit.max_hp // 4)
            and "arm_injury" not in hero.wounds and len(hero.wounds) < 2):
        hero.wounds.append("arm_injury")
    if policy == "serious" and not unit.alive and len(hero.wounds) < 2:
        if "leg_injury" not in hero.wounds:
            hero.wounds.append("leg_injury")


RECRUIT_FIELDS = ("name", "kind", "max_hp", "max_mp", "attack", "magic",
                  "defense", "magic_defense", "speed", "move", "jump",
                  "weapon", "weapon_power", "attack_range", "min_range",
                  "skills", "tags")


def capture_prisoner(unit):
    return {key: getattr(unit, key) for key in RECRUIT_FIELDS}


def inject_recruits(mission, recruits):
    """Stable 1x1 companion spawns; skip missions with no deployment capacity."""
    blocked = {pos for pos in mission.board.cells() if mission.board.tile(pos).blocked}
    occupied = set().union(*(u.occupied_cells() for u in mission.units))
    occupied.update(tuple(o["pos"]) for o in mission.objects)
    for uid, row in sorted(recruits.items()):
        actor_id = "recruit_" + uid
        if any(unit.id == actor_id for unit in mission.units):
            continue
        cell = next((cell for cell in mission.board.cells()
                     if cell not in blocked and cell not in occupied), None)
        if cell is None:
            continue
        attributes = dict(row)
        attributes["tags"] = [t for t in row["tags"]
                              if t != "reload:empty" and not t.startswith("doctrine:")]
        attributes["kind"] = "character"
        unit = Unit(id=actor_id, name=attributes.pop("name"), team="player",
                    pos=tuple(cell), **attributes)
        mission.units.append(unit)
        occupied.add(cell)
