"""R27.C contextual puzzle affordances for the existing canonical Player.

This module is a *read-only* projection of a detached Battle. All advertised
actions are checked against the real engine on disposable previews and are
still revalidated by Simulation.execute when clicked.
"""
from __future__ import annotations

from copy import deepcopy

from sporebound.model import RuleError, distance

PUZZLE_KINDS = frozenset({"key", "plate", "block"})
CONTEXT_LIMIT = 16
STATUS_LIMIT = 48


def _puzzle_mission(objects):
    return any(o["kind"] in PUZZLE_KINDS
               or (o["kind"] == "door" and
                   ("sequence" in o or "key" in o))
               for o in objects)


def contextual_puzzle(battle, selected=None):
    """Return detached, serializable options and state of canonical objects.

    Never calls Battle.execute on the live game, never guesses key/door
    availability from a UI-only duplicate rule, and never modifies the RNG.
    """
    if battle is None or not _puzzle_mission(battle.mission.objects):
        return {"enabled": False, "actions": [], "status": []}
    objects = battle.mission.objects
    status = []
    for obj in objects:
        kind = obj["kind"]
        if kind == "door":
            if "sequence" in obj:
                status.append({"id": obj["id"], "kind": "door",
                               "label": "Porte · " + obj["id"],
                               "detail": "Ouverte" if obj.get("open", False)
                               else "Leviers {}/{}".format(
                                   obj.get("sequence_progress", 0),
                                   len(obj["sequence"]))})
            elif "key" in obj:
                key = next((k for k in objects if k["id"] == obj["key"]), None)
                status.append({"id": obj["id"], "kind": "door",
                               "label": "Porte · " + obj["id"],
                               "detail": "Ouverte" if obj.get("open", False)
                               else "Clé acquise" if key and key.get("used", False)
                               else "Clé manquante"})
            elif any(p["kind"] == "plate" and p.get("link") == obj["id"]
                     for p in objects):
                status.append({"id": obj["id"], "kind": "door",
                               "label": "Porte · " + obj["id"],
                               "detail": "Ouverte" if obj.get("open", False)
                               else "Plaques inactives"})
        elif kind in ("key", "plate", "block"):
            detail = ("Récupérée" if obj.get("used", False) else "À récupérer"
                      if kind == "key" else
                      "Activée" if obj.get("used", False) else "Inactive"
                      if kind == "plate" else
                      "Case {},{}".format(*obj["pos"]))
            status.append({"id": obj["id"], "kind": kind,
                           "label": {"key": "Clé", "plate": "Plaque",
                                     "block": "Bloc"}[kind] + " · " + obj["id"],
                           "detail": detail})
    result = {"enabled": True, "actions": [], "status": status[:STATUS_LIMIT]}
    active = battle.active
    if (active is None or active.team != "player" or
            battle.deploying or battle.result):
        return result

    from sporebound.building_gameplay import toggle_door
    from sporebound.puzzle_rules import push_block

    for obj in objects:
        kind = obj["kind"]
        if kind not in ("key", "switch", "chest", "door", "block"):
            continue
        if kind == "door" and (
                "sequence" in obj or
                any(p["kind"] == "plate" and p.get("link") == obj["id"]
                    for p in objects)):
            continue  # A controlled gate is operated through its puzzle.
        position = tuple(obj["pos"])
        if min(distance(c, position) for c in active.occupied_cells()) > 1:
            continue
        if kind == "block":
            dx, dy = position[0] - active.pos[0], position[1] - active.pos[1]
            if abs(dx) + abs(dy) != 1:
                continue
            command = {"kind": "puzzle_push", "object": obj["id"],
                       "direction": [dx, dy]}
            label = "Pousser · " + obj["id"]
            try:
                preview = deepcopy(battle)
                push_block(preview, preview.active, obj["id"], [dx, dy])
                permitted, reason = True, ""
            except RuleError as exc:
                permitted, reason = False, str(exc)
        elif kind == "door" and "key" not in obj:
            command = {"kind": "door_toggle", "object": obj["id"]}
            label = ("Fermer" if obj.get("open", False) else "Ouvrir") + " · " + obj["id"]
            try:
                preview = deepcopy(battle)
                toggle_door(preview, preview.active, obj["id"])
                permitted, reason = True, ""
            except RuleError as exc:
                permitted, reason = False, str(exc)
        else:
            command = {"kind": "interact", "object": obj["id"]}
            label = ({"key": "Ramasser", "chest": "Ouvrir",
                      "switch": "Actionner", "door": "Déverrouiller"}[kind] +
                     " · " + obj["id"])
            permitted = battle.can_interact(active, obj["id"])
            reason = "" if permitted else "Action indisponible (position, état ou prérequis)"
        result["actions"].append({"id": obj["id"], "kind": kind,
                                   "label": label, "enabled": permitted,
                                   "reason": reason, "command": command,
                                   "selected": list(position) == list(selected or ())})
        if len(result["actions"]) >= CONTEXT_LIMIT:
            break
    result["actions"].sort(key=lambda a: (not a["selected"], a["id"]))
    return result
