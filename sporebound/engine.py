"""Deterministic turn-based rules. No GUI, filesystem or Godot dependency."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import heapq
import json
import random
import uuid

from .model import Cell, Content, Effect, RuleError, Skill, Tile, Unit, distance, require


class Battle:
    def __init__(self, content: Content, mission_id: str, seed: int = 1, battle_id: str | None = None):
        require(mission_id in content.missions, "Unknown mission")
        self.content = deepcopy(content)
        self.mission = deepcopy(content.missions[mission_id])
        self.units = self.mission.units
        self.board = self.mission.board
        self.seed = seed
        self.battle_id = battle_id or str(uuid.uuid4())
        self.rng = random.Random(seed)
        self.tick = 0
        self.active_id: str | None = None
        self.result: str | None = None
        self.hold_ticks = 0
        self.events: list[dict] = []
        self.commands: list[dict] = []
        self.fired: list[str] = []
        self.zones: list[dict] = []
        self.prepared_reactions: dict[str, dict] = {}
        self.inventory = {"player": {"potion": 3, "ether": 2, "phoenix": 1},
                          "enemy": {"potion": 1, "ether": 0, "phoenix": 0}}
        self.loot = 0
        self.relic_pos = self.mission.relic
        self.carrier = None
        for obj in self.mission.objects:
            if obj["kind"] == "door":
                self.board.tiles[tuple(obj["pos"])] = deepcopy(self.board.tile(tuple(obj["pos"])))
                self.board.tiles[tuple(obj["pos"])].blocked = not obj.get("open", False)
        for unit in self.units:
            self._collect(unit)
        self._advance()

    @property
    def active(self) -> Unit | None:
        return self.unit(self.active_id) if self.active_id else None

    def unit(self, uid: str) -> Unit:
        return next(u for u in self.units if u.id == uid)

    def at(self, pos: Cell, alive: bool = True) -> Unit | None:
        return next((u for u in self.units if u.pos == pos and u.alive == alive), None)

    def emit(self, kind: str, **data):
        self.events.append({"tick": self.tick, "kind": kind, **data})

    def _outcome(self):
        if self.result:
            return
        players = [u for u in self.units if u.team == "player" and u.alive]
        enemies = [u for u in self.units if u.team == "enemy" and u.alive]
        m = self.mission
        if not players or (m.protected_id and not self.unit(m.protected_id).alive):
            self.result = "defeat"
        elif m.objective == "eliminate" and not enemies:
            self.result = "victory"
        elif m.objective == "survive" and self.tick >= m.target_ticks:
            self.result = "victory"
        elif m.objective == "extract" and any(u.pos in m.goal for u in players):
            self.result = "victory"
        elif m.objective == "hold" and self.hold_ticks >= m.target_ticks:
            self.result = "victory"
        elif m.objective == "crown" and self.carrier and self.unit(self.carrier).pos in m.goal:
            self.result = "victory"
        if self.result:
            self.emit("battle_end", result=self.result)
            self.active_id = None

    def _collect(self, unit):
        if unit.alive and unit.team == "player" and unit.pos == self.relic_pos:
            self.carrier, self.relic_pos = unit.id, None
            self.emit("relic_taken", unit=unit.id)

    def _triggers(self):
        for trigger in self.mission.triggers:
            if trigger["id"] in self.fired:
                continue
            condition = trigger["condition"]
            matches = (condition == "tick" and self.tick >= trigger["value"] or
                       condition == "enter" and any(u.alive and u.team == "player" and u.pos == tuple(trigger["pos"]) for u in self.units) or
                       condition == "defeated" and not self.unit(trigger["unit"]).alive)
            if not matches:
                continue
            self.fired.append(trigger["id"])
            self.emit("trigger", id=trigger["id"])
            for action in trigger["actions"]:
                if action["kind"] == "hazard":
                    c = tuple(action["pos"])
                    self.board.tiles[c] = deepcopy(self.board.tile(c))
                    self.board.tiles[c].hazard = action["amount"]
                elif action["kind"] == "status":
                    self._status(self.unit(action["unit"]), action["status"], action["duration"])
                else:
                    self.emit("message", text=action.get("text", ""))

    def _advance(self):
        """Stable roster tie-break; time moves only when nobody is ready."""
        for _ in range(10001):
            self._triggers()
            self._outcome()
            if self.result:
                return
            for u in self.units:
                if u.alive and u.ct >= 100 and not {"sleep", "stop"} & u.statuses.keys():
                    if u.id in self.prepared_reactions:
                        self.prepared_reactions.pop(u.id, None)
                        self.emit("prepared_expired", unit=u.id)
                    self.active_id = u.id
                    u.moved = "dont_move" in u.statuses
                    u.acted = "dont_act" in u.statuses
                    u.disengaging = False
                    self.emit("activation", unit=u.id, ct=u.ct)
                    return
            self.tick += 1
            if any(u.alive and u.team == "player" and u.pos in self.mission.goal for u in self.units) and not any(u.alive and u.team == "enemy" and u.pos in self.mission.goal for u in self.units):
                self.hold_ticks += 1
            else:
                self.hold_ticks = 0
            for u in self.units:
                if not u.alive:
                    continue
                if not {"sleep", "stop"} & u.statuses.keys():
                    gain = u.speed
                    if "haste" in u.statuses:
                        gain = gain * 3 // 2
                    if "slow" in u.statuses:
                        gain = max(1, gain // 2)
                    u.ct += gain
                for status in list(u.statuses):
                    if u.statuses[status] > 0:
                        u.statuses[status] -= 1
                        if u.statuses[status] == 0:
                            del u.statuses[status]
                            self.emit("status_expired", unit=u.id, status=status)
                if u.cast:
                    u.cast["remaining"] -= 1
            # All CT/status clocks advance before slow actions resolve in roster order.
            for u in self.units:
                if u.alive and u.cast and u.cast["remaining"] <= 0:
                    pending = u.cast
                    u.cast = None
                    skill = self.content.skills[pending["skill"]]
                    target = self.unit(pending["unit"]) if pending.get("unit") else None
                    cell = target.pos if target else tuple(pending["cell"])
                    if u.mp < skill.cost or (skill.magical and "silence" in u.statuses):
                        self.emit("cast_failed", unit=u.id, skill=skill.id)
                    else:
                        u.mp -= skill.cost
                        self._resolve(u, skill, cell)
            for zone in list(self.zones):
                zone["remaining"] -= 1
                if zone["remaining"] <= 0:
                    self.zones.remove(zone)
        self.result = "draw"
        self.emit("battle_end", result="draw", reason="no activation within 10000 ticks")

    def reachable(self, unit: Unit | None = None) -> dict[Cell, tuple[int, list[Cell]]]:
        u = unit or self.active
        if not u or not u.alive or u.moved or "dont_move" in u.statuses:
            return {}
        blocked = {o.pos for o in self.units if o.alive and o.id != u.id}
        if u.movement == "teleport":
            return {c: (distance(u.pos, c), [u.pos, c]) for c in self.board.cells()
                    if c not in blocked and not self.board.tile(c).blocked and distance(u.pos, c) <= u.movement_budget + 5}
        result = {u.pos: (0, [u.pos])}
        queue = [(0, u.pos)]
        while queue:
            cost, c = heapq.heappop(queue)
            if cost != result[c][0]:
                continue
            for nxt in self.board.neighbors(c):
                tile = self.board.tile(nxt)
                if tile.blocked or nxt in blocked:
                    continue
                if u.movement != "ignore_height" and abs(tile.height - self.board.tile(c).height) > u.jump:
                    continue
                total = cost + tile.cost
                if total <= u.movement_budget and (nxt not in result or total < result[nxt][0]):
                    result[nxt] = total, result[c][1] + [nxt]
                    heapq.heappush(queue, (total, nxt))
        return result

    def line_of_sight(self, start: Cell, end: Cell) -> bool:
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
        high = max(self.board.tile(start).height, self.board.tile(end).height) + 1
        return all(not self.board.tile(c).blocked and self.board.tile(c).height <= high
                   for c in cells if c not in {start, end} and self.board.contains(c))

    def engagement_range(self, u: Unit) -> int:
        if u.engagement_range >= 0:
            return u.engagement_range
        if u.weapon == "spear":
            return 2
        if u.weapon in {"melee", "unarmed"}:
            return 1
        return 0

    def engaged_by(self, u: Unit) -> list[Unit]:
        return [e for e in self.units if e.alive and e.team != u.team
                and self.engagement_range(e) > 0
                and distance(e.pos, u.pos) <= self.engagement_range(e)
                and self.line_of_sight(e.pos, u.pos)]

    def engagement_threats(self, cell: Cell, moving_team: str) -> list[dict]:
        result = []
        for enemy in self.units:
            if not enemy.alive or enemy.team == moving_team:
                continue
            radius = self.engagement_range(enemy)
            if radius and distance(enemy.pos, cell) <= radius and self.line_of_sight(enemy.pos, cell):
                result.append({"unit": enemy.id, "kind": "engagement", "range": radius})
        return result

    def reaction_threats(self, cell: Cell, moving_team: str) -> list[dict]:
        result = []
        for uid, prep in sorted(self.prepared_reactions.items()):
            watcher = self.unit(uid)
            if not watcher.alive or watcher.team == moving_team or not self._can_react(watcher):
                continue
            if prep["mode"] == "overwatch":
                skill = self._basic(watcher)
                d = distance(watcher.pos, cell)
                if skill.min_range <= d <= skill.range and self.line_of_sight(watcher.pos, cell):
                    result.append({"unit": uid, "kind": "overwatch", "cell": cell})
            elif prep["mode"] == "guard":
                radius = self.engagement_range(watcher)
                if radius and distance(watcher.pos, cell) <= radius:
                    result.append({"unit": uid, "kind": "guard", "cell": cell})
        return result

    def movement_threats(self, u: Unit, path: list[Cell]) -> list[dict]:
        """Pure path analysis for UI/AI: engagement entries and reactions that may trigger."""
        require(bool(path) and path[0] == u.pos, "Threat path must start at unit position")
        result = []
        previous = path[0]
        engaged = {row["unit"] for row in self.engagement_threats(previous, u.team)}
        seen_prepared = set()
        for cell in path[1:]:
            after = {row["unit"] for row in self.engagement_threats(cell, u.team)}
            for uid in sorted(after - engaged):
                result.append({"kind": "engagement", "unit": uid, "cell": cell,
                               "chance": 1.0, "amount": 0})
            if not u.disengaging:
                for uid in sorted(engaged - after):
                    enemy = self.unit(uid)
                    if enemy.reaction == "opportunity" and self._can_react(enemy):
                        skill = self._basic(enemy)
                        ghost = deepcopy(u)
                        ghost.pos = previous
                        if skill.min_range <= distance(enemy.pos, previous) <= skill.range and self.line_of_sight(enemy.pos, previous):
                            result.append({"kind": "opportunity", "unit": uid, "cell": previous,
                                           "chance": enemy.brave / 100 * self.hit_chance(enemy, ghost, skill),
                                           "amount": self.damage(enemy, ghost, skill, skill.effects[0])})
            for uid, prep in sorted(self.prepared_reactions.items()):
                if uid in seen_prepared:
                    continue
                watcher = self.unit(uid)
                if not watcher.alive or watcher.team == u.team or not self._can_react(watcher):
                    continue
                ghost = deepcopy(u)
                ghost.pos = cell
                if prep["mode"] == "overwatch":
                    skill = self._basic(watcher)
                    d = distance(watcher.pos, cell)
                    if skill.min_range <= d <= skill.range and self.line_of_sight(watcher.pos, cell):
                        result.append({"kind": "overwatch", "unit": uid, "cell": cell,
                                       "chance": self.hit_chance(watcher, ghost, skill),
                                       "amount": self.damage(watcher, ghost, skill, skill.effects[0])})
                        seen_prepared.add(uid)
                elif prep["mode"] == "guard":
                    radius = self.engagement_range(watcher)
                    if (radius and distance(previous, watcher.pos) > radius
                            and distance(cell, watcher.pos) <= radius
                            and self.line_of_sight(watcher.pos, cell)):
                        skill = self._basic(watcher)
                        if skill.min_range <= distance(watcher.pos, cell) <= skill.range:
                            result.append({"kind": "guard", "unit": uid, "cell": cell,
                                           "chance": self.hit_chance(watcher, ghost, skill),
                                           "amount": self.damage(watcher, ghost, skill, skill.effects[0])})
                            seen_prepared.add(uid)
            previous = cell
            engaged = after
        return result

    def _basic(self, u: Unit) -> Skill:
        fixed_range = max(u.attack_range, 2) if u.weapon == "spear" else u.attack_range
        attack_range = fixed_range if u.attack_range_mode == "fixed" else max(1, self.board.width + self.board.height - 2)
        optimal = u.optimal_range or (u.attack_range if u.attack_range_mode == "los" else 0)
        return Skill("attack", "Attaque", [Effect()], range=attack_range, min_range=u.min_range,
                     optimal_range=optimal, falloff_per_tile=u.falloff_per_tile)

    def _skill(self, u: Unit, sid: str) -> Skill:
        if sid == "attack":
            return self._basic(u)
        require(sid in u.skills, "Skill not in loadout")
        return self.content.skills[sid]

    def _target(self, u: Unit, s: Skill, cell: Cell):
        require(self.board.contains(cell), "Target outside board")
        require(s.min_range <= distance(u.pos, cell) <= s.range, "Target outside range")
        require(not s.los or self.line_of_sight(u.pos, cell), "Line of sight blocked")
        target = self.at(cell, alive=s.target != "downed")
        require(s.target == "ground" or target is not None, "No valid target")
        if s.target == "enemy":
            require(target.team != u.team, "Must target an enemy")
        elif s.target in {"ally", "downed"}:
            require(target.team == u.team, "Must target an ally")
        elif s.target == "self":
            require(target.id == u.id, "Must target self")
        if s.target == "downed":
            require(self.at(cell) is None and not self.board.tile(cell).blocked, "Revive cell occupied or blocked")
        return target

    def _area(self, cell: Cell, s: Skill) -> set[Cell]:
        return {c for c in self.board.cells()
                if (max(abs(c[0] - cell[0]), abs(c[1] - cell[1])) <= s.radius if s.shape == "square"
                    else distance(c, cell) <= s.radius and (s.shape != "cross" or c[0] == cell[0] or c[1] == cell[1]))}

    def _affected(self, caster: Unit, skill: Skill, cell: Cell, effect: Effect):
        area = self._area(cell, skill)
        return [t for t in self.units if t.pos in area and (not t.alive if effect.kind == "revive" else t.alive)
                and (effect.scope in {"all", "target"} or (t.team == caster.team) == (effect.scope == "allies"))]

    def hit_chance(self, caster: Unit, target: Unit, skill: Skill) -> float:
        if target.team == caster.team and skill.target in {"ally", "self", "downed"}:
            return 1.0
        chance = skill.accuracy / 100
        d = distance(caster.pos, target.pos)
        if skill.optimal_range and d > skill.optimal_range and skill.falloff_per_tile:
            chance *= max(0, 100 - (d - skill.optimal_range) * skill.falloff_per_tile) / 100
        if skill.id == "attack" and caster.weapon == "ranged" and self.engaged_by(caster):
            chance *= 0.65
        if target.cast or {"sleep", "stop"} & target.statuses.keys():
            return chance
        if skill.magical:
            return chance * (1 - target.magic_evade / 100)
        if caster.support != "concentrate":
            dx, dy = caster.pos[0] - target.pos[0], caster.pos[1] - target.pos[1]
            dot = dx * target.facing[0] + dy * target.facing[1]
            layers = [target.accessory_evade]
            if dot >= 0:
                layers += [target.shield_evade, target.weapon_evade]
            if dot > 0:
                layers += [target.class_evade]
            for evade in layers:
                chance *= 1 - evade / 100
        if target.reaction == "blade_grasp" and self._can_react(target):
            chance *= 1 - target.brave / 100
        return chance

    def damage(self, caster: Unit, target: Unit, skill: Skill, effect: Effect) -> int:
        if skill.id == "attack":
            power = caster.attack
            if caster.weapon == "focus":
                power = caster.magic
            elif caster.weapon == "ranged":
                power = (caster.attack + caster.speed) // 2
            elif caster.weapon == "unarmed":
                return self._mitigate(caster, target, skill, effect, caster.attack * caster.attack * caster.brave // 100)
            raw = power * caster.weapon_power
        elif skill.magical:
            raw = effect.power * caster.magic * caster.faith * target.faith // 10000
        else:
            raw = caster.attack * effect.power
        return self._mitigate(caster, target, skill, effect, raw)

    def _mitigate(self, caster, target, skill, effect, raw):
        support = "magic_attack_up" if skill.magical else "attack_up"
        defense = "magic_defense_up" if skill.magical else "defense_up"
        if caster.support == support:
            raw = raw * 4 // 3
        if target.support == defense:
            raw = raw * 2 // 3
        if ("shell" if skill.magical else "protect") in target.statuses:
            raw = raw * 2 // 3
        if "guard" in target.statuses:
            raw //= 2
        if target.cast and not skill.magical:
            raw = raw * 3 // 2
        raw = max(0, raw - (target.magic_defense if skill.magical else target.defense))
        return max(0, raw * (100 - target.resistances.get(effect.element, 0)) // 100)

    def forecast(self, skill_id: str, cell: Cell, unit: Unit | None = None) -> list[dict]:
        """Pure forecast: never consume RNG, MP or mutate cast/turn state."""
        u = unit or self.active
        require(u is not None, "No active unit")
        require(not u.acted and "dont_act" not in u.statuses, "Action unavailable")
        s = self._skill(u, skill_id)
        require(u.mp >= s.cost, "Not enough MP")
        require(not s.magical or "silence" not in u.statuses, "Silenced")
        self._target(u, s, cell)
        result = []
        for e in s.effects:
            for t in self._affected(u, s, cell, e):
                result.append({"unit": t.id, "kind": e.kind, "chance": self.hit_chance(u, t, s),
                               "amount": self.damage(u, t, s, e) if e.kind == "damage" else
                               min(e.power, t.max_hp - t.hp) if e.kind == "heal" else
                               min(e.power, t.max_mp - t.mp) if e.kind == "mp" else e.power,
                               "status": e.status})
        if skill_id == "attack":
            target = self.at(cell)
            if target is not None and target.team != u.team:
                for tactic in self.available_team_tactics(u, target):
                    partner = self.unit(tactic["partner"])
                    basic = self._basic(partner)
                    result.append({"unit": target.id, "kind": "tactic",
                                   "chance": self.hit_chance(u, target, s) * self.hit_chance(partner, target, basic),
                                   "amount": max(1, self.damage(partner, target, basic, basic.effects[0]) // 2),
                                   "status": "", "tactic": tactic["id"], "partner": partner.id})
        return result

    def _can_react(self, u: Unit) -> bool:
        return u.alive and not {"sleep", "stop", "dont_act"} & u.statuses.keys()

    def _status(self, u: Unit, status: str, duration: int):
        opposite = {"haste": "slow", "slow": "haste", "poison": "regen", "regen": "poison"}
        u.statuses.pop(opposite.get(status, ""), None)
        previous = u.statuses.get(status, 0)
        u.statuses[status] = -1 if previous == -1 or duration == -1 else max(duration, previous)
        if status in {"sleep", "stop", "silence"} and u.cast:
            # Silence interrupts magic only; Stop/Sleep interrupt all casts.
            if status != "silence" or self.content.skills[u.cast["skill"]].magical:
                u.cast = None
                self.emit("cast_cancelled", unit=u.id)
        if status in {"sleep", "stop", "dont_act"} and u.id in self.prepared_reactions:
            self.prepared_reactions.pop(u.id, None)
            self.emit("prepared_cancelled", unit=u.id, reason=status)
        self.emit("status", unit=u.id, status=status, duration=duration)

    def _hurt(self, target: Unit, amount: int, source: Unit | None = None, reactions=True):
        if not target.alive:
            return
        reactive = source is not None and source.team != target.team and reactions and self._can_react(target)
        if reactive and target.reaction == "mp_switch" and target.mp > 0 and self.rng.randrange(100) < target.brave:
            target.mp = max(0, target.mp - amount)
            self.emit("mp_switch", unit=target.id, amount=amount)
            return
        actual = min(target.hp, amount)
        target.hp -= actual
        if actual:
            target.statuses.pop("sleep", None)
        self.emit("damage", unit=target.id, source=source.id if source else None, amount=actual)
        if not target.alive:
            if self.carrier == target.id:
                self.relic_pos, self.carrier = target.pos, None
                self.emit("relic_dropped", unit=target.id, cell=target.pos)
            target.cast = None
            target.ct = 0
            target.statuses.clear()
            if target.id in self.prepared_reactions:
                self.prepared_reactions.pop(target.id, None)
                self.emit("prepared_cancelled", unit=target.id, reason="downed")
            self.emit("downed", unit=target.id, source=source.id if source else None)
        elif reactive and actual and target.reaction == "auto_potion" and self.inventory[target.team]["potion"] > 0 and self.rng.randrange(100) < target.brave:
            self.inventory[target.team]["potion"] -= 1
            self._heal(target, 25)
        elif reactive and actual and target.reaction == "counter" and source.alive and self.rng.randrange(100) < target.brave:
            s = self._basic(target)
            if s.min_range <= distance(target.pos, source.pos) <= s.range and self.line_of_sight(target.pos, source.pos):
                if self.rng.random() < self.hit_chance(target, source, s):
                    self._hurt(source, self.damage(target, source, s, s.effects[0]), target, reactions=False)
                    self.emit("counter", unit=target.id, target=source.id)

    def _heal(self, target, amount):
        actual = min(amount, target.max_hp - target.hp)
        target.hp += actual
        self.emit("heal", unit=target.id, amount=actual)

    def _displace(self, caster, target, amount, pull=False):
        prep = self.prepared_reactions.get(target.id)
        if prep and prep.get("mode") == "brace" and prep.get("charges", 0) > 0:
            absorbed = min(amount, 2)
            amount -= absorbed
            prep["charges"] -= 1
            target.ct = max(0, target.ct - prep.get("ct_tax", 20))
            self.emit("brace", unit=target.id, source=caster.id, absorbed=absorbed)
            if prep["charges"] <= 0:
                self.prepared_reactions.pop(target.id, None)
            if amount <= 0:
                return
        dx, dy = target.pos[0] - caster.pos[0], target.pos[1] - caster.pos[1]
        if not dx and not dy:
            return
        direction = ((1 if dx > 0 else -1), 0) if abs(dx) >= abs(dy) else (0, (1 if dy > 0 else -1))
        if pull:
            direction = -direction[0], -direction[1]
        for _ in range(amount):
            nxt = target.pos[0] + direction[0], target.pos[1] + direction[1]
            if not self.board.contains(nxt) or self.board.tile(nxt).blocked or self.at(nxt):
                break
            drop = self.board.tile(target.pos).height - self.board.tile(nxt).height
            if drop < -target.jump:
                break
            target.pos = nxt
            self._hurt(target, max(0, drop - target.jump) * 5 + self.board.tile(nxt).hazard)
            self._collect(target)
            if not target.alive:
                break
        self.emit("displace", unit=target.id, pos=target.pos)

    def _resolve(self, caster: Unit, skill: Skill, cell: Cell):
        self.emit("skill", unit=caster.id, skill=skill.id, cell=cell)
        # One accuracy roll per victim, shared by a skill's chained effects.
        rolls = {}
        for e in skill.effects:
            if e.kind == "zone":
                self.zones.append({"cells": sorted(self._area(cell, skill)), "remaining": e.duration,
                                   "power": e.power, "team": caster.team, "scope": e.scope})
                continue
            for target in self._affected(caster, skill, cell, e):
                if target.id not in rolls:
                    rolls[target.id] = self.rng.random() < self.hit_chance(caster, target, skill)
                    if not rolls[target.id]:
                        self.emit("miss", unit=caster.id, target=target.id)
                if not rolls[target.id]:
                    continue
                if e.kind == "damage":
                    self._hurt(target, self.damage(caster, target, skill, e), caster)
                elif e.kind == "heal" and target.alive:
                    self._heal(target, e.power)
                elif e.kind == "revive" and not target.alive and self.at(target.pos) is None and not self.board.tile(target.pos).blocked:
                    target.hp = min(target.max_hp, max(1, e.power))
                    target.ct = 0
                    self.emit("revive", unit=target.id, source=caster.id)
                elif e.kind == "status" and target.alive:
                    self._status(target, e.status, e.duration)
                elif e.kind == "cleanse":
                    target.statuses.pop(e.status, None)
                elif e.kind == "mp":
                    target.mp = min(target.max_mp, target.mp + e.power)
                elif e.kind in {"push", "pull"} and target.alive:
                    self._displace(caster, target, e.power, e.kind == "pull")
        if skill.id == "attack":
            primary = self.at(cell)
            if primary is not None and primary.alive and primary.team != caster.team and rolls.get(primary.id, False):
                self._resolve_team_tactic(caster, primary)
        self._triggers()
        self._outcome()

    def _prepared_attack(self, watcher: Unit, mover: Unit, mode: str):
        prep = self.prepared_reactions.get(watcher.id)
        if not prep or prep.get("charges", 0) <= 0 or not self._can_react(watcher) or not mover.alive:
            return
        skill = self._basic(watcher)
        d = distance(watcher.pos, mover.pos)
        if not (skill.min_range <= d <= skill.range) or not self.line_of_sight(watcher.pos, mover.pos):
            return
        prep["charges"] -= 1
        watcher.ct = max(0, watcher.ct - prep.get("ct_tax", 20))
        self.emit("prepared_triggered", unit=watcher.id, target=mover.id, mode=mode)
        if self.rng.random() < self.hit_chance(watcher, mover, skill):
            self._hurt(mover, self.damage(watcher, mover, skill, skill.effects[0]), watcher, reactions=False)
        else:
            self.emit("miss", unit=watcher.id, target=mover.id)
        if prep["charges"] <= 0:
            self.prepared_reactions.pop(watcher.id, None)

    def _prepared_on_move(self, mover: Unit, previous: Cell):
        for uid in list(self.prepared_reactions):
            if not mover.alive:
                break
            watcher = self.unit(uid)
            if watcher.team == mover.team or not watcher.alive:
                continue
            prep = self.prepared_reactions.get(uid)
            if not prep:
                continue
            if prep["mode"] == "overwatch":
                self._prepared_attack(watcher, mover, "overwatch")
            elif prep["mode"] == "guard":
                radius = self.engagement_range(watcher)
                if radius and distance(previous, watcher.pos) > radius and distance(mover.pos, watcher.pos) <= radius:
                    self._prepared_attack(watcher, mover, "guard")

    def _prepare(self, u: Unit, mode: str):
        require(not u.acted and "dont_act" not in u.statuses, "Action unavailable")
        require(mode in {"overwatch", "guard", "brace"}, "Unknown preparation")
        if mode == "overwatch":
            require(u.weapon == "ranged", "Overwatch requires a ranged weapon")
            require(not self.engaged_by(u), "Cannot prepare Overwatch while engaged")
        elif mode == "guard":
            require(self.engagement_range(u) > 0, "Guard requires an engagement zone")
        else:
            require(self.engagement_range(u) > 0, "Brace requires a close-combat control zone")
        u.acted = True
        u.cast = None
        self.prepared_reactions[u.id] = {"mode": mode, "charges": 1, "ct_tax": 20}
        self.emit("prepared", unit=u.id, mode=mode)

    def available_team_tactics(self, caster: Unit, target: Unit) -> list[dict]:
        if "pincer" not in caster.tactics or not target.alive or target.team == caster.team:
            return []
        if self.engagement_range(caster) <= 0 or distance(caster.pos, target.pos) > self.engagement_range(caster):
            return []
        cx, cy = caster.pos[0] - target.pos[0], caster.pos[1] - target.pos[1]
        result = []
        for ally in self.units:
            if ally.id == caster.id or not ally.alive or ally.team != caster.team or "pincer" not in ally.tactics:
                continue
            if not self._can_react(ally) or ally.ct < 20 or self.engagement_range(ally) <= 0:
                continue
            if distance(ally.pos, target.pos) > self.engagement_range(ally):
                continue
            ax, ay = ally.pos[0] - target.pos[0], ally.pos[1] - target.pos[1]
            opposite = (cx == 0 and ax == 0 and cy * ay < 0) or (cy == 0 and ay == 0 and cx * ax < 0)
            if opposite:
                result.append({"id": "pincer", "partner": ally.id, "target": target.id, "ct_cost": 20})
        return sorted(result, key=lambda row: row["partner"])

    def _resolve_team_tactic(self, caster: Unit, target: Unit):
        options = self.available_team_tactics(caster, target)
        if not options or not target.alive:
            return
        tactic = options[0]
        partner = self.unit(tactic["partner"])
        skill = self._basic(partner)
        partner.ct = max(0, partner.ct - tactic["ct_cost"])
        self.emit("tactic", tactic="pincer", units=[caster.id, partner.id], target=target.id,
                  ct_cost=tactic["ct_cost"])
        if self.rng.random() < self.hit_chance(partner, target, skill):
            amount = max(1, self.damage(partner, target, skill, skill.effects[0]) // 2)
            self._hurt(target, amount, partner, reactions=False)
        else:
            self.emit("miss", unit=partner.id, target=target.id)

    def _move(self, u: Unit, cell: Cell):
        if u.id in self.prepared_reactions:
            self.prepared_reactions.pop(u.id, None)
            self.emit("prepared_cancelled", unit=u.id, reason="moved")
        paths = self.reachable(u)
        require(cell != u.pos and cell in paths, "Destination unreachable or movement spent")
        cost, path = paths[cell]
        u.moved = True
        if u.movement == "teleport" and self.rng.randrange(100) >= max(0, 100 - 10 * max(0, cost - u.movement_budget)):
            self.emit("teleport_failed", unit=u.id, cell=cell)
            return
        for nxt in path[1:]:
            previous = u.pos
            before_engaged = {e.id for e in self.engaged_by(u)}
            for enemy in self.units:
                radius = self.engagement_range(enemy)
                if not u.disengaging and enemy.team != u.team and enemy.reaction == "opportunity" and self._can_react(enemy) and radius > 0 and distance(previous, enemy.pos) <= radius and distance(nxt, enemy.pos) > radius:
                    if self.rng.randrange(100) < enemy.brave:
                        s = self._basic(enemy)
                        if self.rng.random() < self.hit_chance(enemy, u, s):
                            self._hurt(u, self.damage(enemy, u, s, s.effects[0]), enemy, reactions=False)
            if not u.alive:
                break
            u.pos = nxt
            after_engaged = {e.id for e in self.engaged_by(u)}
            for uid in sorted(after_engaged - before_engaged):
                self.emit("engagement_entered", unit=u.id, enemy=uid)
            for uid in sorted(before_engaged - after_engaged):
                self.emit("engagement_left", unit=u.id, enemy=uid)
            self._prepared_on_move(u, previous)
            if not u.alive:
                break
            self._hurt(u, self.board.tile(nxt).hazard) if self.board.tile(nxt).hazard else None
            self._collect(u)
            self._triggers()
            self._outcome()
            if self.result or not u.alive or {"sleep", "stop", "dont_move"} & u.statuses.keys():
                break
        if u.movement == "move_mp_up" and u.alive:
            u.mp = min(u.max_mp, u.mp + max(1, u.max_mp // 10))
        if u.disengaging:
            self.emit("disengaged", unit=u.id)
            u.disengaging = False
        self.emit("move", unit=u.id, start=path[0], end=u.pos, cost=cost)

    def _act(self, u, skill_id, cell):
        require(not u.acted and "dont_act" not in u.statuses, "Action already spent or sealed")
        skill = self._skill(u, skill_id)
        require(u.mp >= skill.cost, "Not enough MP")
        require(not skill.magical or "silence" not in u.statuses, "Silenced")
        target = self._target(u, skill, cell)
        u.acted = True
        if u.cast:
            self.emit("cast_cancelled", unit=u.id)
        u.cast = None
        if skill.cast_ticks:
            ticks = max(1, skill.cast_ticks // 2) if u.support == "short_charge" else skill.cast_ticks
            u.cast = {"skill": skill.id, "cell": list(cell), "remaining": ticks,
                      "unit": target.id if skill.lock == "unit" and target else None}
            self.emit("charging", unit=u.id, skill=skill.id, ticks=ticks)
        else:
            u.mp -= skill.cost
            self._resolve(u, skill, cell)

    def _disengage(self, u: Unit):
        require(not u.acted and "dont_act" not in u.statuses, "Action unavailable")
        require(bool(self.engaged_by(u)), "Unit is not engaged")
        u.acted = True
        u.cast = None
        u.disengaging = True
        self.emit("disengage_ready", unit=u.id)

    def _item(self, u, item, cell):
        require(not u.acted and "dont_act" not in u.statuses, "Action unavailable")
        require(item in self.inventory[u.team] and self.inventory[u.team][item] > 0, "Item unavailable")
        target = self.at(cell, alive=item != "phoenix")
        require(target is not None and target.team == u.team and distance(u.pos, cell) <= 1, "Invalid item target")
        require(item != "phoenix" or self.at(cell) is None and not self.board.tile(cell).blocked, "Revive cell occupied")
        require(self.line_of_sight(u.pos, cell), "Line of sight blocked")
        self.inventory[u.team][item] -= 1
        u.acted = True
        u.cast = None
        if item == "potion":
            self._heal(target, 25)
        elif item == "ether":
            target.mp = min(target.max_mp, target.mp + 8)
        else:
            target.hp = max(1, target.max_hp // 4)
            target.ct = 0
            self.emit("revive", unit=target.id, source=u.id, item="phoenix")
        self.emit("item", unit=u.id, item=item, target=target.id)

    def _interact(self, u, object_id):
        require(not u.acted and "dont_act" not in u.statuses, "Action unavailable")
        obj = next((o for o in self.mission.objects if o["id"] == object_id), None)
        require(obj is not None and distance(u.pos, tuple(obj["pos"])) <= 1 and not obj.get("used", False), "Object unavailable")
        require(u.team == "player", "Only players can interact")
        if obj["kind"] == "door":
            require(not obj.get("open", False), "Door already open")
            obj["open"] = True
            self.board.tiles[tuple(obj["pos"])].blocked = False
        elif obj["kind"] == "switch":
            door = next(o for o in self.mission.objects if o["id"] == obj["link"])
            door["open"] = True
            self.board.tiles[tuple(door["pos"])].blocked = False
        else:
            self.loot += obj.get("amount", 25)
        obj["used"] = True
        u.acted = True
        u.cast = None
        self.emit("interact", unit=u.id, object=object_id)

    def _end(self, u, facing):
        require(facing in {(0, -1), (0, 1), (-1, 0), (1, 0)}, "Invalid facing")
        u.facing = facing
        u.disengaging = False
        cost = 100 if u.moved and u.acted else 80 if u.moved or u.acted else 60
        u.ct = min(60, max(0, u.ct - cost))
        if "poison" in u.statuses:
            self._hurt(u, max(1, u.max_hp // 8))
        if "regen" in u.statuses and u.alive:
            self._heal(u, max(1, u.max_hp // 8))
        for zone in self.zones:
            if u.alive and u.pos in zone["cells"] and (zone["scope"] in {"all", "target"} or (u.team == zone["team"]) == (zone["scope"] == "allies")):
                self._hurt(u, zone["power"])
        self.emit("end_turn", unit=u.id, cost=cost, ct=u.ct)
        self.active_id = None
        self._advance()

    def execute(self, command: dict):
        """Atomic command boundary for UI, AI and replay; invalid input changes nothing."""
        require(self.active is not None and not self.result, "Battle is not accepting commands")
        snapshot = deepcopy(self.__dict__)
        try:
            u = self.active
            require(command.get("unit", u.id) == u.id, "Not this unit's turn")
            kind = command.get("kind")
            if kind in {"move", "act", "item"}:
                raw = command["cell"]
                require(isinstance(raw, (list, tuple)) and len(raw) == 2 and all(type(v) is int for v in raw), "Invalid cell")
                cell = tuple(raw)
            if kind == "move":
                self._move(u, cell)
            elif kind == "act":
                self._act(u, command["skill"], cell)
            elif kind == "item":
                self._item(u, command["item"], cell)
            elif kind == "disengage":
                self._disengage(u)
            elif kind == "interact":
                self._interact(u, command["object"])
            elif kind == "prepare":
                self._prepare(u, command["mode"])
            elif kind == "end":
                self._end(u, tuple(command.get("facing", u.facing)))
            else:
                raise RuleError("Unknown command")
            self.commands.append(deepcopy(command))
            self._outcome()
            if not self.result and self.active and not self.active.alive:
                self.active_id = None
                self._advance()
            elif not self.result and self.active and {"sleep", "stop"} & self.active.statuses.keys():
                self._end(self.active, self.active.facing)
        except (RuleError, KeyError, TypeError, ValueError) as exc:
            self.__dict__ = snapshot
            if isinstance(exc, RuleError):
                raise
            raise RuleError(f"Invalid command: {exc}") from exc

    def state(self) -> dict:
        return {"tick": self.tick, "active": self.active_id, "result": self.result,
                "units": [asdict(u) for u in self.units], "inventory": self.inventory,
                "zones": self.zones, "prepared_reactions": self.prepared_reactions,
                "fired": self.fired, "loot": self.loot,
                "hold_ticks": self.hold_ticks, "objects": self.mission.objects,
                "relic_pos": self.relic_pos, "carrier": self.carrier,
                "tiles": [{"pos": c, **asdict(t)} for c, t in sorted(self.board.tiles.items())],
                "rng": self.rng.getstate(), "events": self.events}

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.state(), sort_keys=True).encode()).hexdigest()

    def recording(self) -> dict:
        return {"version": 1, "battle_id": self.battle_id, "mission": self.mission.id,
                "seed": self.seed, "content": self.content.to_dict(),
                "commands": deepcopy(self.commands), "digest": self.digest()}

    @classmethod
    def replay(cls, recording: dict) -> Battle:
        require(recording.get("version") == 1, "Unsupported replay version")
        battle = cls(Content.from_dict(recording["content"]), recording["mission"],
                     recording["seed"], recording["battle_id"])
        for command in recording["commands"]:
            battle.execute(command)
        require(battle.digest() == recording["digest"], "Replay checksum mismatch")
        return battle
