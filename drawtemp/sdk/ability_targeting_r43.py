"""R43.B3 — read-only CT targeting projection using the *native* Battle rules.

No duplicated LOS, AoE or target-team algorithm. A detached, proposed native
skill is installed into a throwaway Content/Battle. The real session, RNG,
recording, campaign, roster and Player state are NEVER modified.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.ability_contracts import (
    AbilityError, compile_ct_skill, validate_ability,
)
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.engine import Battle
from sporebound.model import Content, RuleError, distance

MAX_TARGET_CELLS = 1024


def _cell(value, board, label):
    if (type(value) not in (list, tuple) or len(value) != 2
            or any(type(n) is not int for n in value)
            or not board.contains(tuple(value))):
        raise AbilityError("invalid_cell", label + " must be a cell inside this mission")
    return tuple(value)


def native_target_preview(session: AuthoringSession, ability, mission_id,
                          caster_id, aim, *, include_candidates=True):
    """Project one proposed CT ability on an authored mission, no GameSession.

    The *same* Battle._target/_area/_affected and Battle.line_of_sight used by
    the standalone Player decide legality. Fresh Battle initialisation is
    deliberately isolated and does not claim live-GameSession turn readiness.
    """
    if not isinstance(session, AuthoringSession):
        raise AbilityError("invalid_session", "Expected authoritative authoring session")
    authored = validate_ability(ability)
    compiled = compile_ct_skill(authored)  # CT dynamic formulas fail closed.
    if type(mission_id) is not str or type(caster_id) is not str:
        raise AbilityError("invalid_actor", "Mission and caster IDs must be strings")

    original = session.snapshot().to_dict()
    content = deepcopy(original["content"])
    missions = [m for m in content["missions"] if m["id"] == mission_id]
    if len(missions) != 1:
        raise AbilityError("missing_mission", "Mission does not exist")
    mission = missions[0]
    actors = [a for a in mission["units"] if a["id"] == caster_id]
    if len(actors) != 1 or type(actors[0]["id"]) is not str:
        raise AbilityError("missing_actor", "Caster absent from the mission")
    # Draft native CT ability replaces a matching canonical skill only inside
    # the throwaway Content: never write to the real authoring snapshot.
    content["skills"] = [row for row in content["skills"]
                         if row["id"] != authored["id"]]
    content["skills"].append(compiled)
    if authored["id"] not in actors[0].get("skills", ()):
        actors[0]["skills"] = [*actors[0].get("skills", ()), authored["id"]]
    battle = Battle(Content.from_dict(content), mission_id, seed=1)
    caster = battle.unit(caster_id)
    if not caster.alive:
        raise AbilityError("inactive_actor", "Caster is not alive")
    if battle.unit_levels.get(caster_id, 0):
        # Battle._target supports only basic shots on upper floors. A versioned
        # height/floor adapter is required before CT abilities can bind there.
        raise AbilityError("unsupported_floor", "Ability targeting on upper floors unavailable")
    tile = _cell(aim, battle.board, "Target")
    skill = battle.content.skills[authored["id"]]
    legal, reason = True, ""
    try:
        battle._target(caster, skill, tile)
    except RuleError as exc:
        legal, reason = False, str(exc)
    area = sorted(battle._area(tile, skill), key=lambda c: (c[1], c[0]))
    recipients = []
    if legal:
        for index, effect in enumerate(skill.effects):
            for affected in battle._affected(caster, skill, tile, effect):
                recipients.append({
                    "effect_index": index, "kind": effect.kind,
                    "scope": effect.scope, "unit": affected.id,
                    "team": affected.team,
                })
    available = []
    if include_candidates:
        origin = caster.pos
        candidates = sorted((
            c for c in battle.board.cells()
            if skill.min_range <= min(distance(occupied, c)
                                      for occupied in caster.occupied_cells()) <= skill.range
        ), key=lambda c: (c[1], c[0]))
        if len(candidates) > MAX_TARGET_CELLS:
            raise AbilityError("target_budget", "Mission needs paged target preview")
        for c in candidates:
            try:
                battle._target(caster, skill, c)
                available.append(list(c))
            except RuleError:
                pass
    return {
        "mission": mission_id, "caster": caster_id,
        "origin": list(caster.pos), "aim": list(tile),
        "legal": legal, "rejection": reason, "area": [list(c) for c in area],
        "available": available, "recipients": recipients,
        "line_of_sight": battle.line_of_sight(caster.pos, tile),
        "notes": (
            "Projection native Battle CT d'un état de mission détaché; "
            "pas de vérification du tour GameSession, de RNG, de MP ni "
            "de rendu de combat. Aucun changement du projet."
        ),
    }


__all__ = ["native_target_preview", "MAX_TARGET_CELLS"]
