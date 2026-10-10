"""Validated, one-shot causal links between otherwise independent tactical fronts.

Each link consumes a *Battle event*, never a speculative AI prediction. Effects
are deterministic, may target unopened battles and can be replayed from the
MultiFrontSession operation journal.
"""
from copy import deepcopy

from .model import require

EVENTS = {"interact", "gate_breached", "defense_sabotaged",
          "passage_installed", "battle_end"}
EFFECTS = {"open_door", "disable_defense", "reduce_opposition",
           "reduce_strength",
           "block_reinforcements"}
EVENT_FIELDS = {"interact": "object", "gate_breached": "gate",
                "defense_sabotaged": "object", "passage_installed": "object",
                "battle_end": "result"}


def _object(content, missions, front, oid):
    mission = content.missions[missions[front]]
    return next((obj for obj in mission.objects if obj["id"] == oid), None)


def validate(content, missions, links):
    require(isinstance(links, list), "Front links must be a list")
    seen = set()
    for link in links:
        require(isinstance(link, dict)
                and set(link) == {"id", "source", "event", "match", "effects"},
                "Invalid front link fields")
        lid, source, event = link["id"], link["source"], link["event"]
        require(isinstance(lid, str) and bool(lid) and lid not in seen,
                "Duplicate or invalid front link id")
        seen.add(lid)
        require(isinstance(source, str) and source in missions
                and isinstance(event, str) and event in EVENTS,
                "Invalid front event source")
        require(isinstance(link["match"], dict)
                and set(link["match"]) == {EVENT_FIELDS[event]},
                "Front event match must specify its event field")
        field = EVENT_FIELDS[event]
        value = link["match"][field]
        require(isinstance(value, str) and bool(value),
                "Invalid front event match")
        if event == "battle_end":
            require(value in {"victory", "defeat"}, "Invalid result match")
        else:
            obj = _object(content, missions, source, value)
            expect = {"gate_breached": "door", "passage_installed": "passage",
                      "defense_sabotaged": "defense"}.get(event)
            require(obj is not None and (expect is None or obj["kind"] == expect),
                    "Unknown or incompatible source object")
            if event == "interact":
                require(obj["kind"] not in {"defense", "passage"},
                        "Defense and passage interactions emit specialized events")
        require(isinstance(link["effects"], list)
                and 0 < len(link["effects"]) <= 16,
                "Front link needs 1..16 effects")
        for effect in link["effects"]:
            require(isinstance(effect, dict)
                    and isinstance(effect.get("kind"), str)
                    and effect["kind"] in EFFECTS
                    and isinstance(effect.get("front"), str)
                    and effect["front"] in missions, "Unknown front effect")
            require(effect["front"] != source, "Front links must cross fronts")
            kind = effect["kind"]
            fields = ({"kind", "front", "object"} if kind in
                      {"open_door", "disable_defense"} else
                      {"kind", "front", "amount"} if kind in {"reduce_opposition", "reduce_strength"}
                      else {"kind", "front"})
            require(set(effect) == fields, "Invalid front effect fields")
            if kind in {"reduce_opposition", "reduce_strength"}:
                amount = effect["amount"]
                require(type(amount) is int and 1 <= amount <= 10000,
                        "Invalid front opposition reduction")
            if kind in {"open_door", "disable_defense"}:
                oid = effect["object"]
                require(isinstance(oid, str) and bool(oid),
                        "Invalid target object id")
                obj = _object(content, missions, effect["front"], oid)
                expected_kind = "door" if kind == "open_door" else "defense"
                require(obj is not None and obj["kind"] == expected_kind,
                        "Unknown or incompatible target object")


def _suppress_waves(battle):
    """Only block reinforcements that have not already spawned."""
    battle.encounter.pending.clear()
    for trigger in battle.mission.triggers:
        trigger["actions"] = [action for action in trigger["actions"]
                              if action["kind"] not in {"queue_wave", "wave"}]


def configure_mission(content, mission_id, overrides, suppress):
    """Prepare the content *before* constructing Battle (tick-zero safety)."""
    if not overrides and not suppress:
        return
    mission = content.missions[mission_id]
    for obj in mission.objects:
        obj.update(deepcopy(overrides.get(obj["id"], {})))
    if suppress:
        for trigger in mission.triggers:
            trigger["actions"] = [action for action in trigger["actions"]
                                  if action["kind"] not in {"queue_wave", "wave"}]


def _modify_object(session, front, oid, patch):
    override = session.front_overrides.setdefault(front, {}).setdefault(oid, {})
    override.update(patch)
    battle = session.battles.get(front)
    if battle is None:
        return
    obj = next(obj for obj in battle.mission.objects if obj["id"] == oid)
    obj.update(patch)
    if obj["kind"] == "door" and obj.get("open"):
        cell = tuple(obj["pos"])
        battle.board.tiles[cell] = deepcopy(battle.board.tile(cell))
        battle.board.tiles[cell].blocked = False
    battle.emit("front_object_changed", object=oid, patch=deepcopy(patch))


def _reduce_force(session, front, amount, *, field, losing_team, result):
    row = session.timeline.fronts[front]
    if row["status"] != "active":
        return
    loss = min(amount, row[field])
    row[field] -= loss
    battle = session.battles.get(front)
    if battle is not None:
        session._apply_attrition(battle, losing_team, loss)
    if row[field] == 0:
        row["status"] = result
        if battle is not None and battle.result is None:
            session._apply_attrition(battle, losing_team, 1000000)
            battle.result = result
            battle.active_id = None
            battle.emit("battle_end", result=result)


def apply(session, link):
    """Called only from the transactional focused Battle command boundary."""
    for effect in link["effects"]:
        kind, front = effect["kind"], effect["front"]
        if kind == "open_door":
            _modify_object(session, front, effect["object"], {"open": True})
        elif kind == "disable_defense":
            _modify_object(session, front, effect["object"], {"disabled": True})
        elif kind == "reduce_opposition":
            _reduce_force(session, front, effect["amount"], field="opposition",
                          losing_team="enemy", result="victory")
        elif kind == "reduce_strength":
            _reduce_force(session, front, effect["amount"], field="strength",
                          losing_team="player", result="defeat")
        else:
            session.blocked_reinforcements.add(front)
            session.pending_reinforcements.pop(front, None)
            if front in session.battles:
                _suppress_waves(session.battles[front])
                session.battles[front].emit("reinforcements_blocked")
    session.applied_links.add(link["id"])
    session.timeline.events.append({"turn": session.timeline.turn,
                                    "kind": "front_link_applied", "link": link["id"],
                                    "source": link["source"]})


def match(link, event):
    return (event["kind"] == link["event"]
            and all(event.get(key) == value
                    for key, value in link["match"].items()))
