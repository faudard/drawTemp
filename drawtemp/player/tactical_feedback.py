"""R12.5/R12.6: read-only tactical presentation from the canonical Battle.

Only the R1 Simulation facade invokes this adapter. Every numerical prediction
comes from Battle.forecast, Battle.reachable, Battle.movement_threats or the
shared tactical_intents / battle_frame projections; no Player combat formulas.
"""
from copy import deepcopy

from sporebound.model import RuleError
from sporebound.presentation import battle_frame
from sporebound.player_ux import combat_hud


DANGER_PRIORITY = {"hazard": 4, "prepared": 3, "cast": 2, "charge": 1}


def build_feedback(battle, selected, skill_id="attack", *, revision=0):
    """Return detached JSON-compatible facts, never predicted AI commitments."""
    if battle is None:
        return None
    if (type(selected) not in (list, tuple) or len(selected) != 2 or
            any(type(v) is not int for v in selected) or
            not battle.board.contains(tuple(selected))):
        raise ValueError("Case tactique hors carte")
    if type(skill_id) is not str or not skill_id or len(skill_id) > 80:
        raise ValueError("Compétence tactique invalide")

    # Some old engine projections are read-only by contract but can traverse
    # rules with custom hooks; prevent even a broken hook from mutating live RNG.
    shadow = deepcopy(battle)
    cell = tuple(selected)
    frame = battle_frame(shadow, selected=cell, skill=skill_id)
    hud = combat_hud(frame, shadow.mission.objective, cell)
    active = shadow.active
    from .puzzle_context import contextual_puzzle
    puzzle = contextual_puzzle(shadow, selected=cell)
    can_act = bool(active and active.alive and active.team == "player" and
                   not shadow.deploying and not shadow.result)
    reachable = {}
    if can_act and not active.moved:
        reachable = shadow.reachable(active)

    move_info = None
    if cell in reachable and active and cell != tuple(active.pos):
        cost, path = reachable[cell]
        move_info = {
            "cost": cost,
            "path": [list(point) for point in path],
            "risks": deepcopy(shadow.movement_threats(active, path)),
        }

    forecast = []
    forecast_error = ""
    can_target = False
    line_of_sight = None
    if can_act:
        line_of_sight = bool(shadow.line_of_sight(active.pos, cell))
        if shadow.status_blocks(active, "act") or active.acted:
            forecast_error = "Action déjà utilisée ou indisponible"
        else:
            try:
                forecast = deepcopy(shadow.forecast(skill_id, cell, active))
                # An empty ground-skill forecast can still be a legal action.
                can_target = True
            except RuleError as exc:
                forecast_error = str(exc)

    overlay = {}
    for point in reachable:
        if point != tuple(active.pos):
            overlay[point] = {"x": point[0], "y": point[1],
                              "kind": "reachable", "certainty": "known"}
    for row in frame.danger:
        pos = tuple(row["cell"])
        previous = overlay.get(pos, {})
        if (previous.get("kind") not in DANGER_PRIORITY or
                DANGER_PRIORITY[row["kind"]] >= DANGER_PRIORITY[previous["kind"]]):
            overlay[pos] = {"x": pos[0], "y": pos[1],
                            "kind": row["kind"], "certainty": row["certainty"]}
    tile_heights = {t.pos: t.height for t in frame.tiles}
    markers = []
    for point, marker in sorted(overlay.items()):
        markers.append({**marker, "height": tile_heights.get(point, 0)})
    if len(markers) > 4096:
        markers = markers[:4096]  # Visual bounding only; complete details remain below.

    focus = {"cell": list(cell), "can_target": can_target,
             "line_of_sight": line_of_sight, "forecast": forecast,
             "error": forecast_error, "move": move_info,
             "danger": [deepcopy(d) for d in frame.danger if tuple(d["cell"]) == cell]}
    active_data = None
    if active:
        active_data = {"id": active.id, "name": active.name, "team": active.team,
                       "hp": active.hp, "max_hp": active.max_hp,
                       "mp": active.mp, "max_mp": active.max_mp,
                       "ct": active.ct, "moved": active.moved, "acted": active.acted,
                       "skills": ["attack", *active.skills],
                       "statuses": sorted(active.statuses)}

    return {"source_revision": revision, "skill": skill_id,
            "active": active_data, "objective": hud.objective,
            "headline": hud.headline, "selection_summary": hud.selection_summary,
            "warnings": list(hud.warnings), "roster": list(hud.roster),
            "timeline": [deepcopy(row) for row in frame.timeline],
            "casts": [deepcopy(row) for row in frame.casts],
            "charges": [deepcopy(row) for row in frame.charges],
            "squads": [deepcopy(row) for row in frame.squads],
            "danger": [deepcopy(row) for row in frame.danger],
            "reachable": [list(point) for point in sorted(reachable)],
            "focus": focus, "markers": markers,
            "result": shadow.result, "deploying": shadow.deploying,
            "puzzle": puzzle}
