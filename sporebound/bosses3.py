"""Data-authored boss phases, deterministic multi-cell growth and siege hooks (2.7.5).

Author with an existing hp_below trigger and a boss_phase action. Existing
queue_wave/spawn/message actions compose with it; no separate boss engine.
"""
from __future__ import annotations

from .model import require

PHASE = "boss_phase:"


def validate_phase(context, action):
    require(set(action) <= {"kind", "unit", "phase", "form", "bonuses", "footprint"},
            "Unsupported boss phase property")
    context.unit(action["unit"])
    context.integer(action["phase"], 2, 8)
    require(isinstance(action.get("form", ""), str) and
            len(action.get("form", "")) <= 64, "Invalid boss form")
    bonuses = action.get("bonuses", {})
    require(isinstance(bonuses, dict) and
            set(bonuses) <= {"attack", "magic", "defense", "magic_defense",
                             "speed", "move", "weapon_power", "max_hp"},
            "Invalid boss bonus")
    for value in bonuses.values():
        context.integer(value, 0, 100)
    footprint = action.get("footprint")
    if footprint is not None:
        require(isinstance(footprint, (tuple, list)) and len(footprint) == 2,
                "Invalid boss footprint")
        for side in footprint:
            context.integer(side, 1, 4)


def boss_phase(battle, action):
    unit = next((u for u in battle.units if u.id == action["unit"]), None)
    require(unit is not None and unit.alive, "Boss is not alive")
    current = int(next((tag[len(PHASE):] for tag in unit.tags
                        if tag.startswith(PHASE)), "1"))
    require(action["phase"] > current, "Boss phase must advance")
    footprint = tuple(action.get("footprint", unit.footprint))
    cells = {(unit.pos[0] + x, unit.pos[1] + y)
             for x in range(footprint[0]) for y in range(footprint[1])}
    occupied = set().union(*(other.occupied_cells() for other in battle.units
                             if other.alive and other.id != unit.id))
    require(all(battle.board.contains(cell) and not battle.board.tile(cell).blocked
                and cell not in occupied for cell in cells),
            "Boss transformation overlaps terrain or units")
    unit.footprint = footprint
    for key, bonus in action.get("bonuses", {}).items():
        setattr(unit, key, getattr(unit, key) + bonus)
    unit.tags = [tag for tag in unit.tags if not tag.startswith(PHASE)]
    unit.tags.append(PHASE + str(action["phase"]))
    battle.emit("boss_phase", unit=unit.id, phase=action["phase"],
                form=action.get("form", ""), footprint=list(footprint))


def boss_preview(battle, boss_id):
    """Read-only state; scripts still own transitions via normal triggers."""
    unit = next((u for u in battle.units if u.id == boss_id), None)
    require(unit is not None, "Unknown boss")
    phase = next((int(t[len(PHASE):]) for t in unit.tags if t.startswith(PHASE)), 1)
    pending = sorted(
        ({"id": t["id"], "percent": t["percent"]}
         for t in battle.mission.triggers
         if t["condition"] == "hp_below" and t["unit"] == boss_id
         and t["id"] not in battle.fired),
        key=lambda row: (-row["percent"], row["id"]))
    return {"unit": unit.id, "phase": phase, "footprint": list(unit.footprint),
            "hp_percent": 100 * unit.hp // unit.max_hp, "pending": pending}


def install_bosses(rules):
    from .rules.registry import TriggerActionRule
    return rules.with_family("trigger_actions", rules.trigger_actions.with_rule(
        "boss_phase", TriggerActionRule(boss_phase, validate_phase, version="2.7.5")))
