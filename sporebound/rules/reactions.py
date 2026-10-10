"""Reactions policies; Battle owns state and transactions."""
from __future__ import annotations

from copy import deepcopy
from . import statuses
from ..model import Cell, Unit, distance, require

def reaction_threats(battle, cell: Cell, moving_team: str) -> list[dict]:
    result = []
    for uid, prep in sorted(battle.prepared_reactions.items()):
        watcher = battle.unit(uid)
        if not watcher.alive or watcher.team == moving_team or not battle._can_react(watcher):
            continue
        if battle.rules.preparations.get(prep['mode']).covers(battle, watcher, cell):
            result.append({'unit': uid, 'kind': prep['mode'], 'cell': cell})
    return result


def movement_threats(battle, u: Unit, path: list[Cell]) -> list[dict]:
    """Pure path analysis for UI/AI: engagement entries and reactions that may trigger."""
    require(bool(path) and path[0] == u.pos, "Threat path must start at unit position")
    result = []
    previous = path[0]
    engaged = {row["unit"] for row in battle.engagement_threats(previous, u.team)}
    seen_prepared = set()
    seen_pursuit = set()
    for cell in path[1:]:
        after = {row["unit"] for row in battle.engagement_threats(cell, u.team)}
        for uid in sorted(after - engaged):
            result.append({"kind": "engagement", "unit": uid, "cell": cell,
                           "chance": 1.0, "amount": 0})
        for uid in sorted(engaged - after):
            enemy = battle.unit(uid)
            row = battle.rules.reactions.get(enemy.reaction).forecast_leave(battle, enemy, u, previous, seen_pursuit)
            if row is not None:
                result.append(row)
        for uid, prep in sorted(battle.prepared_reactions.items()):
            if uid in seen_prepared:
                continue
            watcher = battle.unit(uid)
            if not watcher.alive or watcher.team == u.team or not battle._can_react(watcher):
                continue
            ghost = deepcopy(u)
            ghost.pos = cell
            rule = battle.rules.preparations.get(prep['mode'])
            if rule.enters(battle, watcher, previous, cell):
                skill = battle._basic(watcher)
                if (skill.min_range <= distance(watcher.pos, cell) <= skill.range
                        and battle.line_of_sight(watcher.pos, cell)):
                    result.append({'kind': prep['mode'], 'unit': uid, 'cell': cell,
                                   'chance': battle.hit_chance(watcher, ghost, skill),
                                   'amount': battle.damage(watcher, ghost, skill, skill.effects[0])})
                    seen_prepared.add(uid)
        previous = cell
        engaged = after
    return result


def interceptor_for(battle, target: Unit, source: Unit | None) -> Unit | None:
    if source is None or source.team == target.team:
        return None
    for uid, prep in sorted(battle.prepared_reactions.items()):
        protector = battle.unit(uid)
        if battle.rules.preparations.get(prep['mode']).intercepts(battle, protector, prep, target):
            return protector
    return None


def _hurt(battle, target: Unit, amount: int, source: Unit | None = None, reactions=True):
    if not target.alive:
        return
    if reactions:
        protector = battle.interceptor_for(target, source)
        if protector is not None:
            prep = battle.prepared_reactions.pop(protector.id)
            protector.ct = max(0, protector.ct - prep.get("ct_tax", 20))
            battle.emit("intercept", unit=protector.id, protected=target.id,
                      source=source.id, amount=amount)
            battle._hurt(protector, amount, source, reactions=False)
            return
    reactive = source is not None and source.team != target.team and reactions and battle._can_react(target)
    if reactive and battle.rules.reactions.get(target.reaction).before_damage(battle, target, source, amount):
        return
    actual = min(target.hp, amount)
    target.hp -= actual
    if actual:
        statuses.wake(battle, target)
    battle.emit("damage", unit=target.id, source=source.id if source else None, amount=actual)
    if not target.alive:
        if battle.carrier == target.id:
            battle.relic_pos, battle.carrier = target.pos, None
            battle.emit("relic_dropped", unit=target.id, cell=target.pos)
        target.cast = None
        target.ct = 0
        target.statuses.clear()
        if target.id in battle.prepared_reactions:
            battle.prepared_reactions.pop(target.id, None)
            battle.emit("prepared_cancelled", unit=target.id, reason="downed")
        battle.emit("downed", unit=target.id, source=source.id if source else None)
    elif reactive and actual:
        battle.rules.reactions.get(target.reaction).after_damage(battle, target, source, actual)


def _prepared_attack(battle, watcher: Unit, mover: Unit, mode: str):
    prep = battle.prepared_reactions.get(watcher.id)
    if not prep or prep.get("charges", 0) <= 0 or not battle._can_react(watcher) or not mover.alive:
        return
    skill = battle._basic(watcher)
    d = distance(watcher.pos, mover.pos)
    if not (skill.min_range <= d <= skill.range) or not battle.line_of_sight(watcher.pos, mover.pos):
        return
    prep["charges"] -= 1
    watcher.ct = max(0, watcher.ct - prep.get("ct_tax", 20))
    battle.emit("prepared_triggered", unit=watcher.id, target=mover.id, mode=mode)
    if battle.rng.random() < battle.hit_chance(watcher, mover, skill):
        battle._hurt(mover, battle.damage(watcher, mover, skill, skill.effects[0]), watcher, reactions=False)
    else:
        battle.emit("miss", unit=watcher.id, target=mover.id)
    if prep["charges"] <= 0:
        battle.prepared_reactions.pop(watcher.id, None)


def _prepared_on_move(battle, mover: Unit, previous: Cell):
    for uid in list(battle.prepared_reactions):
        if not mover.alive:
            break
        watcher = battle.unit(uid)
        if watcher.team == mover.team or not watcher.alive:
            continue
        prep = battle.prepared_reactions.get(uid)
        if not prep:
            continue
        if battle.rules.preparations.get(prep['mode']).enters(battle, watcher, previous, mover.pos):
            battle._prepared_attack(watcher, mover, prep['mode'])


def _prepare(battle, u: Unit, mode: str, target_id: str | None = None):
    require(not u.acted and not battle.status_blocks(u, "act"), "Action unavailable")
    rule = battle.rules.preparations.get(mode)
    rule.validate(battle, u, target_id)
    u.acted = True
    u.cast = None
    battle.prepared_reactions[u.id] = {"mode": mode, "charges": 1, "ct_tax": 20}
    if rule.targeted:
        battle.prepared_reactions[u.id]["target"] = target_id
    battle.emit("prepared", unit=u.id, mode=mode)


