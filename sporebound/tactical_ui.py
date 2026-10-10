"""Read-only tactical presentation contract for both Player and Studio.

Renderers consume these snapshots; all combat formulas and command legality
remain in Battle, formations3, coordinated_ai and bosses3. No UI imports.
"""
from __future__ import annotations

from .model import RuleError, require


def tactical_snapshot(battle, cell=None):
    """Return a JSON-serializable, deterministic view without changing Battle."""
    from .bosses3 import boss_intent_preview
    from .coordinated_ai import squad_focus_preview
    from .formations3 import formation_control_map, formation_preview
    from .synergies3 import synergy_readiness

    if cell is not None:
        require(isinstance(cell, (tuple, list)) and len(cell) == 2
                and all(type(n) is int for n in cell)
                and battle.board.contains(tuple(cell)), "Selected cell outside board")
    selected = tuple(cell) if cell is not None else None
    enhanced = "formation" in battle.rules.commands
    view = {"selected": list(selected) if selected else None,
            "enhanced": enhanced, "formations": [], "zones": [],
            "bosses": [], "focus": [], "synergies": [],
            "attack": [], "movement_threats": []}
    if not enhanced:
        return view
    for unit in sorted(battle.units, key=lambda u: u.id):
        if unit.alive and any(tag.startswith("formation:") for tag in unit.tags):
            view["formations"].append(formation_preview(battle, unit.id))
        if unit.alive and (unit.behavior == "phase_boss"
                           or any(tag.startswith("boss_phase:") for tag in unit.tags)):
            view["bosses"].append(boss_intent_preview(battle, unit.id))
    for team in ("player", "enemy"):
        view["zones"].extend({"team": team, **row}
                             for row in formation_control_map(battle, team))
    actor = battle.active
    if actor is None or battle.deploying or battle.result:
        return view
    if not actor.acted:
        view["focus"] = squad_focus_preview(battle, actor.id)
    if selected is None:
        return view
    victim = battle.at(selected)
    if victim is not None and victim.alive and victim.team != actor.team:
        if not actor.acted:
            try:
                view["attack"] = battle.forecast("attack", selected, actor)
            except RuleError:
                pass
            view["synergies"] = synergy_readiness(battle, actor.id, victim.id)
    if (not actor.moved and "move" in battle.rules.commands
            and selected in battle.reachable(actor)):
        _, path = battle.reachable(actor)[selected]
        view["movement_threats"] = battle.movement_threats(actor, path)
    return view
