"""Movement policies; Battle owns state and transactions."""
from __future__ import annotations

import heapq
from .registry import MovementRule, Registry
from ..model import Cell, Unit, distance, require

def reachable(battle, unit: Unit | None = None) -> dict[Cell, tuple[int, list[Cell]]]:
    u = unit or battle.active
    if not u or not u.alive or u.moved or battle.status_blocks(u, "move"):
        return {}
    blocked = set().union(*(o.occupied_cells() for o in battle.units if o.alive and o.id != u.id))
    def free(anchor):
        cells = u.occupied_cells(anchor)
        return all(battle.board.contains(c) and c not in blocked and not battle.board.tile(c).blocked
                   for c in cells)

    if battle.rules.movements.get(u.movement).teleport:
        return {c: (distance(u.pos, c), [u.pos, c]) for c in battle.board.cells()
                if free(c) and distance(u.pos, c) <= battle.movement_budget(u) + 5}
    result = {u.pos: (0, [u.pos])}
    queue = [(0, u.pos)]
    while queue:
        cost, c = heapq.heappop(queue)
        if cost != result[c][0]:
            continue
        from ..siege import links
        edges = [(nxt, None) for nxt in battle.board.neighbors(c)]
        edges.extend(links(battle, c))
        for nxt, passage_cost in edges:
            tile = battle.board.tile(nxt)
            if not free(nxt):
                continue
            if passage_cost is None and not battle.can_step_height(u, c, nxt):
                continue
            total = cost + (tile.cost if passage_cost is None else passage_cost)
            if total <= battle.movement_budget(u) and (nxt not in result or total < result[nxt][0]):
                result[nxt] = total, result[c][1] + [nxt]
                heapq.heappush(queue, (total, nxt))
    return result


def line_of_sight(battle, start: Cell, end: Cell) -> bool:
    """Conservative supercover: diagonal shots cannot leak through a corner."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    nx, ny = abs(dx), abs(dy)
    sx, sy = (1 if dx > 0 else -1), (1 if dy > 0 else -1)
    x, y = start
    ix = iy = 0
    cells = []
    while ix < nx or iy < ny:
        decision = (1 + 2 * ix) * ny - (1 + 2 * iy) * nx
        if decision == 0:
            cells.extend([(x + sx, y), (x, y + sy)])
            x, y, ix, iy = x + sx, y + sy, ix + 1, iy + 1
        elif decision < 0:
            x, ix = x + sx, ix + 1
        else:
            y, iy = y + sy, iy + 1
        cells.append((x, y))
    high = max(battle.board.tile(start).height, battle.board.tile(end).height) + 1
    return all(not battle.board.tile(c).blocked and battle.board.tile(c).height <= high
               for c in cells if c not in {start, end} and battle.board.contains(c))


def engagement_range(battle, u: Unit) -> int:
    if u.engagement_range >= 0:
        return u.engagement_range
    if u.weapon == "spear":
        return 2
    if u.weapon in {"melee", "unarmed"}:
        return 1
    return 0


def engaged_by(battle, u: Unit) -> list[Unit]:
    return [e for e in battle.units if e.alive and e.team != u.team
            and battle.engagement_range(e) > 0
            and min(distance(a, b) for a in e.occupied_cells() for b in u.occupied_cells()) <= battle.engagement_range(e)
            and battle.line_of_sight(e.pos, u.pos)]


def engagement_threats(battle, cell: Cell, moving_team: str) -> list[dict]:
    result = []
    for enemy in battle.units:
        if not enemy.alive or enemy.team == moving_team:
            continue
        radius = battle.engagement_range(enemy)
        if radius and min(distance(a, cell) for a in enemy.occupied_cells()) <= radius and battle.line_of_sight(enemy.pos, cell):
            result.append({"unit": enemy.id, "kind": "engagement", "range": radius})
    return result


def charge_options(battle, unit: Unit | None = None) -> list[dict]:
    """Pure charge query for UI/AI: straight approach, minimum two-cell commitment."""
    u = unit or battle.active
    if (u is None or not u.alive or u.moved or u.acted
            or battle.status_blocks(u, "charge")
            or battle.engagement_range(u) <= 0):
        return []
    paths = battle.reachable(u)
    radius = battle.engagement_range(u)
    result = []
    for target in battle.units:
        if not target.alive or target.team == u.team:
            continue
        dx, dy = target.pos[0] - u.pos[0], target.pos[1] - u.pos[1]
        if dx and dy:
            continue
        total = abs(dx) + abs(dy)
        travel = total - radius
        if travel < 2:
            continue
        step = ((1 if dx > 0 else -1), 0) if dx else (0, (1 if dy > 0 else -1))
        landing = (target.pos[0] - step[0] * radius,
                   target.pos[1] - step[1] * radius)
        row = paths.get(landing)
        if row is None:
            continue
        _, path = row
        expected = [(u.pos[0] + step[0] * i, u.pos[1] + step[1] * i)
                    for i in range(travel + 1)]
        if path != expected:
            continue
        result.append({"target": target.id, "cell": target.pos, "landing": landing,
                       "distance": travel, "ct_cost": 20,
                       "threats": battle.movement_threats(u, path)})
    return sorted(result, key=lambda row: (row["target"], row["landing"]))


def _displace(battle, caster, target, amount, pull=False):
    prep = battle.prepared_reactions.get(target.id)
    if prep:
        amount = battle.rules.preparations.get(prep['mode']).displace(battle, target, caster, prep, amount)
        if amount <= 0:
            return
    battle.emit("forced_move", unit=target.id, source=caster.id,
              mode="pull" if pull else "push", amount=amount)
    dx, dy = target.pos[0] - caster.pos[0], target.pos[1] - caster.pos[1]
    if not dx and not dy:
        return
    direction = ((1 if dx > 0 else -1), 0) if abs(dx) >= abs(dy) else (0, (1 if dy > 0 else -1))
    if pull:
        direction = -direction[0], -direction[1]
    for _ in range(amount):
        nxt = target.pos[0] + direction[0], target.pos[1] + direction[1]
        cells = target.occupied_cells(nxt)
        if any(not battle.board.contains(c) or battle.board.tile(c).blocked
               or any(other.alive and other.id != target.id and c in other.occupied_cells()
                      for other in battle.units) for c in cells):
            break
        drop = battle.board.tile(target.pos).height - battle.board.tile(nxt).height
        if drop < -target.jump:
            break
        target.pos = nxt
        forced_damage = max(0, drop - target.jump) * 5 + battle.board.tile(nxt).hazard
        if forced_damage:
            battle._hurt(target, forced_damage, caster, reactions=False)
        battle._collect(target)
        if not target.alive:
            break
    battle.emit("displace", unit=target.id, pos=target.pos, source=caster.id,
              mode="pull" if pull else "push")


def _move(battle, u: Unit, cell: Cell):
    if u.id in battle.prepared_reactions:
        battle.prepared_reactions.pop(u.id, None)
        battle.emit("prepared_cancelled", unit=u.id, reason="moved")
    paths = battle.reachable(u)
    require(cell != u.pos and cell in paths, "Destination unreachable or movement spent")
    cost, path = paths[cell]
    u.moved = True
    if battle.rules.movements.get(u.movement).teleport and battle.rng.randrange(100) >= max(0, 100 - 10 * max(0, cost - battle.movement_budget(u))):
        battle.emit("teleport_failed", unit=u.id, cell=cell)
        return
    pursued = set()
    for nxt in path[1:]:
        previous = u.pos
        before_engaged = {e.id for e in battle.engaged_by(u)}
        pursuers = []
        for enemy in battle.units:
            radius = battle.engagement_range(enemy)
            leaving = (enemy.team != u.team and battle._can_react(enemy) and radius > 0
                       and distance(previous, enemy.pos) <= radius
                       and distance(nxt, enemy.pos) > radius)
            if not leaving:
                continue
            if battle.rules.reactions.get(enemy.reaction).on_leave(battle, enemy, u, previous, pursued):
                pursuers.append(enemy)
        if not u.alive:
            break
        u.pos = nxt
        for pursuer in pursuers:
            if not pursuer.alive or battle.at(previous) is not None:
                continue
            origin = pursuer.pos
            pursuer.pos = previous
            pursuer.ct = max(0, pursuer.ct - 20)
            pursued.add(pursuer.id)
            battle.emit("pursuit", unit=pursuer.id, target=u.id, start=origin,
                      end=previous, ct_cost=20)
            if battle.board.tile(previous).hazard:
                battle._hurt(pursuer, battle.board.tile(previous).hazard, reactions=False)
        after_engaged = {e.id for e in battle.engaged_by(u)}
        for uid in sorted(after_engaged - before_engaged):
            battle.emit("engagement_entered", unit=u.id, enemy=uid)
        for uid in sorted(before_engaged - after_engaged):
            battle.emit("engagement_left", unit=u.id, enemy=uid)
        battle._prepared_on_move(u, previous)
        if not u.alive:
            break
        battle._hurt(u, battle.board.tile(nxt).hazard) if battle.board.tile(nxt).hazard else None
        battle._collect(u)
        battle._triggers()
        battle._outcome()
        if battle.result or not u.alive or battle.status_blocks(u, "continue_move"):
            break
    if u.alive:
        battle.rules.movements.get(u.movement).after_move(battle, u)
    if u.disengaging:
        battle.emit("disengaged", unit=u.id)
        u.disengaging = False
    battle.emit("move", unit=u.id, start=path[0], end=u.pos, cost=cost)


def _charge(battle, u: Unit, target_cell: Cell):
    require(not u.moved and not u.acted, "Charge needs Move and Act")
    option = next((row for row in battle.charge_options(u)
                   if tuple(row["cell"]) == target_cell), None)
    require(option is not None, "Charge needs a clear straight approach of at least two cells")
    target = battle.unit(option["target"])
    u.ct = max(0, u.ct - option["ct_cost"])
    battle.emit("charge_started", unit=u.id, target=target.id,
              landing=option["landing"], distance=option["distance"],
              ct_cost=option["ct_cost"])
    battle._move(u, tuple(option["landing"]))
    if (not u.alive or battle.result or u.pos != tuple(option["landing"])
            or battle.status_blocks(u, "reaction")):
        battle.emit("charge_interrupted", unit=u.id, target=target.id, end=u.pos)
        return
    require(target.alive and target.pos == target_cell, "Charge target no longer available")
    first_event = len(battle.events)
    battle._act(u, "attack", target_cell)
    hit = any(event.get("kind") == "damage" and event.get("source") == u.id
              and event.get("unit") == target.id and event.get("amount", 0) > 0
              for event in battle.events[first_event:])
    pushed = False
    if hit and target.alive:
        before = target.pos
        battle._displace(u, target, 1)
        pushed = target.pos != before
    battle.emit("charge", unit=u.id, target=target.id, distance=option["distance"],
              pushed=pushed, ct_cost=option["ct_cost"])


def _disengage(battle, u: Unit):
    require(not u.acted and not battle.status_blocks(u, "act"), "Action unavailable")
    require(bool(battle.engaged_by(u)), "Unit is not engaged")
    u.acted = True
    u.cast = None
    u.disengaging = True
    battle.emit("disengage_ready", unit=u.id)




def restore_mp(battle, unit):
    unit.mp = min(unit.max_mp, unit.mp + max(1, unit.max_mp // 10))


def default_movements():
    return Registry((('none', MovementRule()), ('move_plus_1', MovementRule(bonus=1)),
                     ('move_plus_2', MovementRule(bonus=2)),
                     ('ignore_height', MovementRule(ignore_height=True)),
                     ('teleport', MovementRule(teleport=True)),
                     ('move_mp_up', MovementRule(after_move=restore_mp))))
