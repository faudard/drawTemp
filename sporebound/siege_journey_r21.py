"""R21.D: an inspectable, replay-safe castle-siege journey.

Only project actual MultiFrontSession and Battle state. Tactical commands,
deployment legality, convoys and focus constraints remain owned by the engine.
This module does not invent a second mission/campaign state machine.
"""
from copy import deepcopy

from .deployment import check_position
from .model import RuleError, require
from .siege_readiness_r21 import siege_front_readiness


def deployment_choices(battle, *, max_cells=8):
    """Legal current placement cells per living player, no hidden mutations.

    Options derive from authored deployment zones and the exact engine
    check_position. Only the display is bounded, not the underlying legality.
    """
    require(type(max_cells) is int and 1 <= max_cells <= 32,
            "Expected 1..32 displayed deployment cells")
    if not battle.deploying:
        return []
    candidates = sorted({
        tuple(cell)
        for zone in battle.mission.deployment
        for cell in zone["cells"]
    })
    result = []
    for actor in sorted(battle.units, key=lambda u: u.id):
        if actor.team != "player" or not actor.alive:
            continue
        valid = []
        for cell in candidates:
            try:
                check_position(battle, actor, cell)
            except RuleError:
                continue
            valid.append(list(cell))
        result.append({
            "unit": actor.id,
            "current": list(actor.pos),
            "valid_count": len(valid),
            "cells": valid[:max_cells],
            "truncated": len(valid) > max_cells,
            "certainty": "legal_now",
        })
    return result


def siege_journey_snapshot(session, *, max_deploy_cells=8):
    """Pure guided view of the next legal siege decisions across all fronts.

    Focus legality uses the real switch handler on an isolated session copy:
    deployment, unfinished CT turns, campaign gates and side skirmishes are
    respected without copying their validation into this presentation layer.
    """
    require(type(max_deploy_cells) is int and 1 <= max_deploy_cells <= 32,
            "Expected 1..32 displayed deployment cells")
    siege = siege_front_readiness(session)
    active = session.active
    phase = ("deployed" if active.deploying else
             "resolved" if active.result else "tactical")
    # Deliberately do not include whole battle snapshots or speculative future
    # actions. The journal is the authority for checkpoint/resume.
    deployment = deployment_choices(active, max_cells=max_deploy_cells)
    focus_choices = []
    for front in sorted(session.missions):
        current = front == session.timeline.focused
        allowed = current
        reason = None
        if not current:
            shadow = deepcopy(session)
            try:
                shadow.switch(front)
                allowed = True
            except RuleError as error:
                reason = str(error)
        focus_choices.append({
            "front": front, "current": current, "ready": allowed,
            "reason": reason,
            "status": session.timeline.fronts[front]["status"],
        })
    cargo = []
    if session.logistics is not None:
        for convoy in sorted(session.logistics.in_transit,
                             key=lambda c: c["id"]):
            cargo.append({
                "id": convoy["id"],
                "source": convoy["from"],
                "destination": convoy["to"],
                "team": convoy["team"],
                "unit_ids": sorted(row["id"] for row in convoy["actors"]),
                "eta_turns": max(0, convoy["arrival"] - session.timeline.turn),
                "stranded": bool(convoy.get("stranded", False)),
                "escorted": bool(convoy.get("escorted", False)),
            })
    hints = []
    if active.deploying:
        hints.append({
            "kind": "deployment",
            "reason": "Place units with legal deploy commands, then start_battle"})
    elif active.result:
        hints.append({
            "kind": "front_result",
            "reason": "Inspect completed objective and choose the next front"})
    else:
        for row in siege["operations"]:
            if row["ready"]:
                hints.append({"kind": "tactical", "command": {
                    "kind": "interact", "object": row["object"]},
                    "reason": "Current interaction is legal (" + row["phase"] + ")"})
    if cargo:
        hints.append({
            "kind": "logistics",
            "reason": "Advance the strategic clock to process in-transit convoys"})
    hints.append({
        "kind": "checkpoint",
        "reason": "Use command-center save/load; authenticated replay validates state"})
    return {
        "focused": session.timeline.focused,
        "turn": session.timeline.turn,
        "phase": phase,
        "actor": active.active_id,
        "fronts": siege["fronts"],
        "deployment": deployment,
        "focus_choices": focus_choices,
        "siege_operations": siege["operations"],
        "causal_links": siege["causal_links"],
        "blocked_reinforcements": siege["blocked_reinforcements"],
        "convoys": cargo,
        "hints": hints,
        "checkpoint_operations": len(session.history),
        "certainty": "legal_current_state_only",
    }
