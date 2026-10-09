"""Deterministic turn-based rules. No GUI, filesystem or Godot dependency."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import random
import uuid

from .rules import default_rules
from .rules import movement, reactions as reaction_rules, statuses, tactics, triggers
from .model import Cell, Content, Effect, RuleError, Skill, Tile, Unit, distance, require


class Battle:
    def __init__(self, content: Content, mission_id: str, seed: int = 1, battle_id: str | None = None, *, rules=None):
        self.rules = rules if rules is not None else default_rules()
        for key in ('damage', 'hit_chance', 'mitigation'):
            self.rules.formulas.get(key)
        content.validate(rules=self.rules)
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
        self.lifetimes: dict[str, int] = {}
        self.summon_owners: dict[str, str] = {}
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
        return next((u for u in self.units if pos in u.occupied_cells() and u.alive == alive), None)

    def emit(self, kind: str, **data):
        self.events.append({"tick": self.tick, "kind": kind, **data})

    def _outcome(self):
        if self.result:
            return
        players = [u for u in self.units if u.team == "player" and u.alive]
        m = self.mission
        if not players or (m.protected_id and not self.unit(m.protected_id).alive):
            self.result = "defeat"
        elif self.rules.objectives.get(m.objective).achieved(self):
            self.result = "victory"
        if self.result:
            self.emit("battle_end", result=self.result)
            self.active_id = None

    def _collect(self, unit):
        if unit.alive and unit.team == "player" and unit.pos == self.relic_pos:
            self.carrier, self.relic_pos = unit.id, None
            self.emit("relic_taken", unit=unit.id)

    def spawn_actor(self, definition, *, lifetime=None, owner_id=None):
        from .lifecycle import spawn
        spec = deepcopy(definition)
        if spec.get("kind") == "summon":
            require(owner_id is not None, "Summon requires owner")
            owner = self.unit(owner_id)
            require(owner.alive, "Summoner must be alive")
            limit = spec.pop("summon_limit", 1)
            require(type(limit) is int and limit > 0, "Summon limit must be positive")
            owned = [uid for uid, oid in self.summon_owners.items() if oid == owner_id]
            require(len(owned) < limit, "Summon limit reached")
        if lifetime is not None:
            require(type(lifetime) is int and lifetime > 0, "Lifetime must be positive")
        actor = spawn(self, spec)
        if lifetime is not None:
            self.lifetimes[actor.id] = self.tick + lifetime
        if owner_id is not None:
            self.summon_owners[actor.id] = owner_id
        return actor

    def spawn_wave(self, actors, *, lifetime=None):
        """Spawn an entire reinforcement wave atomically, including RNG and events."""
        require(isinstance(actors, list) and bool(actors), "Wave needs actors")
        require(sum(u.alive for u in self.units) + len(actors) <= 14,
                "Too many active combatants for a tactical encounter")
        snapshot = deepcopy(self.__dict__)
        try:
            spawned = [self.spawn_actor(spec, lifetime=lifetime) for spec in actors]
            self.emit("reinforcement_wave", units=[actor.id for actor in spawned])
            return spawned
        except Exception:
            self.__dict__ = snapshot
            raise

    def despawn_actor(self, actor_id):
        from .lifecycle import despawn
        actor = despawn(self, actor_id)
        self.lifetimes.pop(actor_id, None)
        self.summon_owners.pop(actor_id, None)
        return actor

    def _expire_actors(self):
        for uid, deadline in list(self.lifetimes.items()):
            if self.tick >= deadline:
                self.despawn_actor(uid)
                self.emit("actor_expired", unit=uid)
        for uid, owner_id in list(self.summon_owners.items()):
            owner = next((u for u in self.units if u.id == owner_id), None)
            if owner is None or not owner.alive:
                self.despawn_actor(uid)
                self.emit("summon_lost", unit=uid, owner=owner_id)

    def _triggers(self):
        self._expire_actors()
        triggers.dispatch(self)

    def _advance(self):
        """Stable roster tie-break; time moves only when nobody is ready."""
        for _ in range(10001):
            self._triggers()
            self._outcome()
            if self.result:
                return
            for u in self.units:
                if u.alive and u.ct >= 100 and not self.status_blocks(u, "activation"):
                    if u.id in self.prepared_reactions:
                        self.prepared_reactions.pop(u.id, None)
                        self.emit("prepared_expired", unit=u.id)
                    self.active_id = u.id
                    u.moved = self.status_blocks(u, "move")
                    u.acted = self.status_blocks(u, "act")
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
                if not self.status_blocks(u, "activation"):
                    u.ct += statuses.speed(self, u)
                statuses.tick(self, u)
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
                    if u.mp < skill.cost or (skill.magical and self.status_blocks(u, "magic")):
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
        return movement.reachable(self, unit)

    def line_of_sight(self, start: Cell, end: Cell) -> bool:
        return movement.line_of_sight(self, start, end)

    def engagement_range(self, u: Unit) -> int:
        return movement.engagement_range(self, u)

    def engaged_by(self, u: Unit) -> list[Unit]:
        return movement.engaged_by(self, u)

    def engagement_threats(self, cell: Cell, moving_team: str) -> list[dict]:
        return movement.engagement_threats(self, cell, moving_team)

    def reaction_threats(self, cell: Cell, moving_team: str) -> list[dict]:
        return reaction_rules.reaction_threats(self, cell, moving_team)

    def movement_threats(self, u: Unit, path: list[Cell]) -> list[dict]:
        return reaction_rules.movement_threats(self, u, path)

    def charge_options(self, unit: Unit | None = None) -> list[dict]:
        return movement.charge_options(self, unit)

    def relay_options(self, unit: Unit | None = None) -> list[dict]:
        return self.rules.tactics.get("relay").reposition(self, unit) if "relay" in self.rules.tactics else []

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
        require(s.min_range <= min(distance(origin, cell) for origin in u.occupied_cells()) <= s.range, "Target outside range")
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
        return [t for t in self.units if not t.occupied_cells().isdisjoint(area) and (not t.alive if self.rules.effects.get(effect.kind).targets_downed else t.alive)
                and (effect.scope in {"all", "target"} or (t.team == caster.team) == (effect.scope == "allies"))]

    def hit_chance(self, caster: Unit, target: Unit, skill: Skill) -> float:
        return self.rules.formulas.get('hit_chance').calculate(self, caster, target, skill)

    def damage(self, caster: Unit, target: Unit, skill: Skill, effect: Effect) -> int:
        return self.rules.formulas.get('damage').calculate(self, caster, target, skill, effect)

    def _mitigate(self, caster, target, skill, effect, raw):
        return self.rules.formulas.get('mitigation').calculate(self, caster, target, skill, effect, raw)

    def forecast(self, skill_id: str, cell: Cell, unit: Unit | None = None) -> list[dict]:
        """Pure forecast: never consume RNG, MP or mutate cast/turn state."""
        u = unit or self.active
        require(u is not None, "No active unit")
        require(not u.acted and not self.status_blocks(u, "act"), "Action unavailable")
        s = self._skill(u, skill_id)
        require(u.mp >= s.cost, "Not enough MP")
        require(not s.magical or not self.status_blocks(u, "magic"), "Silenced")
        self._target(u, s, cell)
        result = []
        for e in s.effects:
            for t in self._affected(u, s, cell, e):
                result.append({"unit": t.id, "kind": e.kind, "chance": self.hit_chance(u, t, s),
                               "amount": self.rules.effects.get(e.kind).amount(self, u, t, s, e),
                               "status": e.status})
        for row in result:
            if row["kind"] == "damage":
                protected = self.unit(row["unit"])
                protector = self.interceptor_for(protected, u)
                if protector is not None:
                    row["redirected_to"] = protector.id
        if skill_id == "attack":
            target = self.at(cell)
            direct = next((row for row in result if row["unit"] == target.id and row["kind"] == "damage"), None) if target else None
            if (target is not None and target.team != u.team and direct is not None
                    and direct["amount"] < target.hp):
                for tactic in self.available_team_tactics(u, target):
                    partner_ids = tactic["partners"] if "partners" in tactic else [tactic["partner"]]
                    divisor = self.rules.tactics.get(tactic["id"]).divisor
                    for partner_id in partner_ids:
                        partner = self.unit(partner_id)
                        basic = self._basic(partner)
                        result.append({"unit": target.id, "kind": "tactic",
                                       "chance": self.hit_chance(u, target, s) * self.hit_chance(partner, target, basic),
                                       "amount": max(1, self.damage(partner, target, basic, basic.effects[0]) // divisor),
                                       "status": "", "tactic": tactic["id"], "partner": partner.id,
                                       "members": [u.id, *partner_ids]})
        return result

    def status_blocks(self, unit: Unit, action: str) -> bool:
        return statuses.blocked(self, unit, action)

    def movement_budget(self, unit: Unit) -> int:
        return unit.move + self.rules.movements.get(unit.movement).bonus

    def can_step_height(self, unit: Unit, start: Cell, end: Cell) -> bool:
        return (self.rules.movements.get(unit.movement).ignore_height
                or abs(self.board.tile(end).height - self.board.tile(start).height) <= unit.jump)

    def _can_react(self, u: Unit) -> bool:
        return u.alive and not self.status_blocks(u, "reaction")

    def _status(self, u: Unit, status: str, duration: int, source: Unit | None = None):
        return statuses._status(self, u, status, duration, source)

    def interceptor_for(self, target: Unit, source: Unit | None) -> Unit | None:
        return reaction_rules.interceptor_for(self, target, source)

    def _hurt(self, target: Unit, amount: int, source: Unit | None = None, reactions=True):
        return reaction_rules._hurt(self, target, amount, source, reactions)

    def _heal(self, target, amount):
        actual = min(amount, target.max_hp - target.hp)
        target.hp += actual
        self.emit("heal", unit=target.id, amount=actual)

    def _displace(self, caster, target, amount, pull=False):
        return movement._displace(self, caster, target, amount, pull)

    def _resolve(self, caster: Unit, skill: Skill, cell: Cell):
        self.emit("skill", unit=caster.id, skill=skill.id, cell=cell)
        # One accuracy roll per victim, shared by a skill's chained effects.
        rolls = {}
        for e in skill.effects:
            rule = self.rules.effects.get(e.kind)
            if rule.area:
                rule.apply(self, caster, None, skill, e, cell)
                continue
            for target in self._affected(caster, skill, cell, e):
                if target.id not in rolls:
                    rolls[target.id] = self.rng.random() < self.hit_chance(caster, target, skill)
                    if not rolls[target.id]:
                        self.emit("miss", unit=caster.id, target=target.id)
                if not rolls[target.id]:
                    continue
                rule.apply(self, caster, target, skill, e, cell)
        if skill.id == "attack":
            primary = self.at(cell)
            if primary is not None and primary.alive and primary.team != caster.team and rolls.get(primary.id, False):
                self._resolve_team_tactic(caster, primary)
        self._triggers()
        self._outcome()

    def _prepared_attack(self, watcher: Unit, mover: Unit, mode: str):
        return reaction_rules._prepared_attack(self, watcher, mover, mode)

    def _prepared_on_move(self, mover: Unit, previous: Cell):
        return reaction_rules._prepared_on_move(self, mover, previous)

    def _prepare(self, u: Unit, mode: str, target_id: str | None = None):
        return reaction_rules._prepare(self, u, mode, target_id)

    def available_team_tactics(self, caster: Unit, target: Unit) -> list[dict]:
        return tactics.available_team_tactics(self, caster, target)

    def _resolve_team_tactic(self, caster: Unit, target: Unit):
        return tactics._resolve_team_tactic(self, caster, target)

    def _move(self, u: Unit, cell: Cell):
        return movement._move(self, u, cell)

    def _act(self, u, skill_id, cell):
        require(not u.acted and not self.status_blocks(u, "act"), "Action already spent or sealed")
        skill = self._skill(u, skill_id)
        require(u.mp >= skill.cost, "Not enough MP")
        require(not skill.magical or not self.status_blocks(u, "magic"), "Silenced")
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

    def _charge(self, u: Unit, target_cell: Cell):
        return movement._charge(self, u, target_cell)

    def _relay(self, u: Unit, partner_id: str, cell: Cell):
        return self.rules.tactics.get("relay").execute(self, u, partner_id, cell)

    def _disengage(self, u: Unit):
        return movement._disengage(self, u)

    def _item(self, u, item, cell):
        require(not u.acted and not self.status_blocks(u, "act"), "Action unavailable")
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
        require(not u.acted and not self.status_blocks(u, "act"), "Action unavailable")
        obj = next((o for o in self.mission.objects if o["id"] == object_id), None)
        require(obj is not None and min(distance(c, tuple(obj["pos"])) for c in u.occupied_cells()) <= 1 and not obj.get("used", False), "Object unavailable")
        require(u.team == "player", "Only players can interact")
        if obj["kind"] in {"ram", "catapult"}:
            target = next(o for o in self.mission.objects if o["id"] == obj["link"])
            require(not target.get("open", False), "Gate already breached")
            if obj["kind"] == "ram" and distance(obj["pos"], target["pos"]) > 1:
                origin = tuple(obj["pos"])
                choices = sorted(
                    (cell for cell in self.board.neighbors(origin)
                     if distance(cell, tuple(target["pos"])) < distance(origin, tuple(target["pos"]))
                     and not self.board.tile(cell).blocked
                     and not any(unit.alive and unit.pos == cell for unit in self.units)
                     and not any(other is not obj and tuple(other["pos"]) == cell
                                 for other in self.mission.objects)),
                    key=lambda cell: (distance(cell, tuple(target["pos"])), cell[1], cell[0]))
                require(bool(choices), "Ram path blocked")
                obj["pos"] = choices[0]
                self.emit("ram_advanced", unit=u.id, engine=obj["id"], pos=choices[0])
                u.acted = True
                u.cast = None
                return
            require(obj["kind"] != "catapult" or distance(obj["pos"], target["pos"]) <= obj.get("range", 8),
                    "Gate out of catapult range")
            target["hp"] = max(0, target.get("hp", 1) - obj.get("power", 1))
            self.emit("siege_hit", unit=u.id, engine=obj["id"], gate=target["id"], hp=target["hp"])
            if target["hp"] == 0:
                target["open"] = True
                self.board.tiles[tuple(target["pos"])].blocked = False
                self.emit("gate_breached", gate=target["id"])
        elif obj["kind"] == "door":
            require(not obj.get("open", False), "Door already open")
            obj["open"] = True
            self.board.tiles[tuple(obj["pos"])].blocked = False
        elif obj["kind"] == "switch":
            door = next(o for o in self.mission.objects if o["id"] == obj["link"])
            door["open"] = True
            self.board.tiles[tuple(door["pos"])].blocked = False
        else:
            self.loot += obj.get("amount", 25)
        if obj["kind"] not in {"ram", "catapult"}:
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
        statuses.end_turn(self, u)
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
            self.rules.commands.get(command.get("kind")).execute(self, u, command)
            self.commands.append(deepcopy(command))
            self._outcome()
            if not self.result and self.active and not self.active.alive:
                self.active_id = None
                self._advance()
            elif not self.result and self.active and self.status_blocks(self.active, "activation"):
                self._end(self.active, self.active.facing)
        except Exception as exc:
            self.__dict__ = snapshot
            if isinstance(exc, RuleError):
                raise
            if isinstance(exc, (KeyError, TypeError, ValueError)):
                raise RuleError(f"Invalid command: {exc}") from exc
            raise

    @staticmethod
    def _unit_state(unit):
        row = asdict(unit)
        for key, default in {'archetype': '', 'kind': 'character', 'tags': [], 'behavior': 'tactical'}.items():
            if row[key] == default:
                del row[key]
        return row

    def state(self) -> dict:
        return {"tick": self.tick, "active": self.active_id, "result": self.result,
                "units": [self._unit_state(u) for u in self.units], "inventory": self.inventory,
                "zones": self.zones, "lifetimes": self.lifetimes, "summon_owners": self.summon_owners, "prepared_reactions": self.prepared_reactions,
                "fired": self.fired, "loot": self.loot,
                "hold_ticks": self.hold_ticks, "objects": self.mission.objects,
                "relic_pos": self.relic_pos, "carrier": self.carrier,
                "tiles": [{"pos": c, **asdict(t)} for c, t in sorted(self.board.tiles.items())],
                "rng": self.rng.getstate(), "events": self.events}

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.state(), sort_keys=True).encode()).hexdigest()

    def recording(self) -> dict:
        return {"version": 3, "rules": self.rules.manifest(), "battle_id": self.battle_id, "mission": self.mission.id,
                "seed": self.seed, "content": self.content.to_dict(),
                "commands": deepcopy(self.commands), "digest": self.digest()}

    @classmethod
    def replay(cls, recording: dict, *, rules=None) -> Battle:
        require(recording.get("version") in {1, 2, 3}, "Unsupported replay version")
        rules = rules if rules is not None else default_rules()
        if recording['version'] == 3:
            require(recording.get('rules') == rules.manifest(), 'Replay ruleset mismatch')
        elif recording['version'] == 2:
            legacy_keys = {'version', 'commands', 'effects', 'objectives', 'behaviors', 'formulas'}
            current = rules.manifest()
            legacy = {key: value for key, value in current.items() if key in legacy_keys}
            require(recording.get('rules') == legacy, 'Replay ruleset mismatch')
            defaults = default_rules().manifest()
            require(all(value == defaults[key] for key, value in current.items() if key not in legacy_keys),
                    'Legacy replay requires default extended rules')
        else:
            require(rules.manifest() == default_rules().manifest(), 'Legacy replay requires default rules')
        battle = cls(Content.from_dict(recording["content"], rules=rules), recording["mission"],
                     recording["seed"], recording["battle_id"], rules=rules)
        for command in recording["commands"]:
            battle.execute(command)
        require(battle.digest() == recording["digest"], "Replay checksum mismatch")
        return battle
