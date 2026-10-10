"""Deterministic utility AI using the exact player rules and pure forecasts."""
from .model import RuleError, distance


def _utility(battle, actor, rows):
    score = 0.0
    for row in rows:
        target = battle.unit(row["unit"])
        friendly = actor.team == target.team
        if row["kind"] == "damage":
            amount = min(row["amount"], target.hp)
            value = amount + (25 if row["amount"] >= target.hp else 0)
            score += (-1.4 if friendly else 1) * value * row["chance"]
        elif row["kind"] == "heal":
            urgency = 1.5 if target.hp * 3 < target.max_hp else 1
            score += (1 if friendly else -1) * min(row["amount"], target.max_hp - target.hp) * row["chance"] * urgency
        elif row["kind"] == "revive" and not target.alive:
            score += 35 if friendly else -35
        elif row["kind"] == "status" and row["status"] not in target.statuses:
            helpful = battle.rules.statuses.get(row["status"]).beneficial
            score += (12 if friendly == helpful else -12) * row["chance"]
        elif row["kind"] == "cleanse" and row["status"] in target.statuses:
            score += 10 if friendly else -10
        elif row["kind"] == "mp":
            score += (1 if friendly else -1) * min(row["amount"], target.max_mp - target.mp)
        elif row["kind"] == "tactic":
            score += (-1.4 if friendly else 1) * min(row["amount"], target.hp) * row["chance"]
    return score


def _path_risk(battle, actor, path):
    rows = battle.movement_threats(actor, path)
    risk = sum(row["amount"] * row["chance"] for row in rows)
    if actor.weapon == "ranged":
        risk += sum(6 for row in rows if row["kind"] == "engagement")
    return risk


def _choose_tactical_command(battle):
    u = battle.active
    if u is None:
        raise RuleError("No active unit")
    opponents = [t for t in battle.units if t.alive and t.team != u.team]
    if u.cast:
        return {"kind": "end"}
    if u.disengaging and 'move' in battle.rules.commands:
        reachable = battle.reachable(u)
        if reachable and opponents:
            best = max(reachable, key=lambda c: (min(distance(c, t.pos) for t in opponents),
                                                 battle.board.tile(c).cover, -reachable[c][0], c))
            if best != u.pos:
                return {"kind": "move", "cell": list(best)}
        return {"kind": "end"}
    if "disengage" in battle.rules.commands and u.weapon == "ranged" and battle.engaged_by(u) and not u.acted and not battle.status_blocks(u, "act"):
        return {"kind": "disengage"}
    origins = {u.pos: (0, [u.pos])}
    if 'move' in battle.rules.commands:
        origins.update(battle.reachable(u))
    # A staffed defense keeps its operator nearby until empty or sabotaged.
    posts = [o for o in battle.mission.objects if o['kind'] == 'defense'
             and o['team'] == u.team and not o.get('disabled') and o.get('charges', 2) > 0
             and distance(u.pos, tuple(o['pos'])) <= 1]
    if posts:
        origins = {c: value for c, value in origins.items()
                   if any(distance(c, tuple(o['pos'])) <= 1 for o in posts)}
    candidates = []
    original = u.pos
    try:
        for origin, (cost, path) in sorted(origins.items()):
            u.pos = original
            path_risk = _path_risk(battle, u, path) if origin != original else 0
            u.pos = origin
            if "act" in battle.rules.commands and not u.acted and not battle.status_blocks(u, "act"):
                for sid in ["attack", *u.skills]:
                    skill = battle._skill(u, sid)
                    if skill.cost > u.mp or skill.magical and battle.status_blocks(u, "magic"):
                        continue
                    cells = list(battle.board.cells()) if skill.target == "ground" else sorted({t.pos for t in battle.units})
                    for cell in cells:
                        try:
                            rows = battle.forecast(sid, cell, u)
                        except RuleError:
                            continue
                        value = _utility(battle, u, rows) / (1 + skill.cast_ticks / 10) - skill.cost * .2
                        value -= sum(battle.board.tile(c).hazard for c in path[1:]) * 1.5 + cost * .05 + path_risk
                        if value > 0:
                            cmd = {"kind": "act", "skill": sid, "cell": list(cell)} if origin == original else {"kind": "move", "cell": list(origin)}
                            candidates.append((value, cmd))
            if "interact" in battle.rules.commands and not u.acted and not battle.status_blocks(u, "act"):
                from .siege import defense_value
                for obj in battle.mission.objects:
                    if obj['kind'] == 'defense' and distance(origin, tuple(obj['pos'])) <= 1:
                        value = defense_value(battle, u, obj) - cost * .05 - path_risk
                        if value > 0:
                            cmd = ({'kind': 'interact', 'object': obj['id']} if origin == original
                                   else {'kind': 'move', 'cell': list(origin)})
                            candidates.append((value, cmd))
            if not u.acted and not battle.status_blocks(u, "act"):
                for obj in battle.mission.objects:
                    if obj['kind'] not in {'ram', 'catapult'}:
                        continue
                    hp = obj.get('hp', obj.get('max_hp', 12))
                    maximum = obj.get('max_hp', hp)
                    if hp <= 0:
                        continue
                    distance_to_engine = min(distance(c, tuple(obj['pos'])) for c in u.occupied_cells(origin))
                    if ('siege_attack' in battle.rules.commands
                            and obj.get('team', 'player') != u.team and distance_to_engine <= 1):
                        amount = max(1, u.attack + u.weapon_power // 2)
                        value = 20 + min(hp, amount) * .8 - cost * .05 - path_risk
                        cmd = ({'kind': 'siege_attack', 'object': obj['id']} if origin == original
                               else {'kind': 'move', 'cell': list(origin)})
                        candidates.append((value, cmd))
                    elif ('repair_siege' in battle.rules.commands
                          and obj.get('team', 'player') == u.team and obj.get('repair_charges', 0) > 0
                          and hp < maximum and distance_to_engine <= 1):
                        amount = min(obj.get('repair', 8), maximum - hp)
                        value = min(amount, maximum - hp) * .7 - cost * .05 - path_risk
                        if value > 0:
                            cmd = ({'kind': 'repair_siege', 'object': obj['id']} if origin == original
                                   else {'kind': 'move', 'cell': list(origin)})
                            candidates.append((value, cmd))
            if origin != original:
                before = min((distance(original, t.pos) for t in opponents), default=0)
                after = min((distance(origin, t.pos) for t in opponents), default=0)
                score = (before - after) * .3 - cost * .05
                if u.team == "player" and battle.mission.objective in {"extract", "hold"}:
                    goals = battle.mission.goal
                    score = (min(distance(original, g) for g in goals) - min(distance(origin, g) for g in goals)) * 2 - cost * .05
                if u.team == "player" and battle.mission.objective == "crown":
                    goals = battle.mission.goal if battle.carrier == u.id else [battle.relic_pos] if battle.relic_pos else []
                    if goals:
                        score = (min(distance(original, g) for g in goals) - min(distance(origin, g) for g in goals)) * 3 - cost * .05
                score -= sum(battle.board.tile(c).hazard for c in path[1:]) * 1.5 + path_risk
                score += battle.board.tile(origin).cover * .001
                if score > 0:
                    candidates.append((score, {"kind": "move", "cell": list(origin)}))
    finally:
        u.pos = original
    if not u.acted and not battle.status_blocks(u, "act"):
        for target in battle.units if "item" in battle.rules.commands else []:
            if target.team != u.team or distance(u.pos, target.pos) > 1 or not battle.line_of_sight(u.pos, target.pos):
                continue
            if target.alive and battle.inventory[u.team]["potion"]:
                urgency = 1.5 if target.hp * 3 < target.max_hp else 1
                value = min(25, target.max_hp - target.hp) * urgency - 5
                if value > 0:
                    candidates.append((value, {"kind": "item", "item": "potion", "cell": list(target.pos)}))
            elif not target.alive and battle.inventory[u.team]["phoenix"] and not battle.at(target.pos) and not battle.board.tile(target.pos).blocked:
                candidates.append((30, {"kind": "item", "item": "phoenix", "cell": list(target.pos)}))
        if "interact" in battle.rules.commands:
            for obj in battle.mission.objects:
                if obj['kind'] == 'defense' and (obj.get('disabled') or obj['team'] == u.team):
                    continue
                if obj['kind'] == 'passage' and obj.get('enabled', True):
                    continue
                if obj['kind'] == 'door' and obj.get('locked'):
                    continue
                if obj['kind'] in {'ram', 'catapult'} and obj.get('team', 'player') != u.team:
                    continue
                if obj['kind'] not in {'ram', 'catapult'} and u.team != 'player':
                    continue
                if obj['kind'] in {'ram', 'catapult'} and any(o['id'] == obj['link'] and o.get('open') for o in battle.mission.objects):
                    continue
                if not obj.get("used") and distance(u.pos, tuple(obj["pos"])) <= 1 and not (obj["kind"] == "door" and obj.get("open")):
                    if battle.can_interact(u, obj["id"]):
                        value = 4
                        if obj['kind'] in {'ram', 'catapult'}:
                            target = next(o for o in battle.mission.objects if o['id'] == obj['link'])
                            value = 16 + (8 if obj['kind'] == 'ram' and distance(obj['pos'], target['pos']) <= 1 else 0)
                        candidates.append((value, {"kind": "interact", "object": obj["id"]}))
    if candidates:
        # Canonical JSON-like string breaks ties independently of dict ordering.
        return sorted(candidates, key=lambda c: (-c[0], str(sorted(c[1].items()))))[0][1]
    if "prepare" in battle.rules.commands and not u.acted and not battle.status_blocks(u, "act"):
        if "overwatch" in battle.rules.preparations and u.weapon == "ranged" and not battle.engaged_by(u):
            return {"kind": "prepare", "mode": "overwatch"}
        if "guard" in battle.rules.preparations and battle.engagement_range(u) > 0 and any(distance(u.pos, t.pos) <= battle.movement_budget(u) + battle.engagement_range(u) for t in opponents):
            return {"kind": "prepare", "mode": "guard"}
    facing = u.facing
    if opponents:
        nearest = min(opponents, key=lambda t: (distance(t.pos, u.pos), t.id))
        dx, dy = nearest.pos[0] - u.pos[0], nearest.pos[1] - u.pos[1]
        facing = (1 if dx > 0 else -1, 0) if abs(dx) > abs(dy) else (0, 1 if dy > 0 else -1)
    return {"kind": "end", "facing": list(facing)}


def play_activation(battle):
    """Bounded to Move + Act + End, including a failed teleport."""
    start = sum(e["kind"] == "activation" for e in battle.events)
    for _ in range(3):
        if battle.result or sum(e["kind"] == "activation" for e in battle.events) != start:
            return
        battle.execute(choose_command(battle))


def simulate(battle, max_commands=1000):
    for _ in range(max_commands):
        if battle.result:
            break
        battle.execute(choose_command(battle))
    return {"result": battle.result or "limit", "ticks": battle.tick,
            "commands": len(battle.commands), "digest": battle.digest()}


def choose_command(battle):
    """Actor behavior selects intent; execution always uses Battle.execute."""
    if battle.deploying:
        return {"kind": "start_battle"}
    actor = battle.active
    if actor is None:
        raise RuleError('No active unit')
    return battle.rules.behaviors.get(actor.behavior).choose(battle)

