"""Typed content contracts shared by simulation, CLI and the editor."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path

Cell = tuple[int, int]
STATUSES = {"poison", "regen", "haste", "slow", "protect", "shell", "silence",
            "sleep", "stop", "dont_move", "dont_act", "guard"}
REACTIONS = {"none", "counter", "opportunity", "pursuit", "blade_grasp", "auto_potion", "mp_switch"}
TEAM_TACTICS = {"pincer", "crossfire", "encirclement", "relay"}
TEAM_TACTIC_ARITY = {"pincer": 2, "crossfire": 2, "encirclement": 3, "relay": 2}
SUPPORTS = {"none", "attack_up", "magic_attack_up", "defense_up", "magic_defense_up",
            "concentrate", "short_charge"}
MOVEMENTS = {"none", "move_plus_1", "move_plus_2", "ignore_height", "teleport", "move_mp_up"}


class RuleError(ValueError):
    """A rejected command or invalid content; suitable for display in the editor."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuleError(message)


def distance(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@dataclass
class Tile:
    height: int = 0
    cost: int = 1
    blocked: bool = False
    cover: int = 0
    hazard: int = 0
    # Presentation-only: simulation still uses height, cost and blocked.
    surface: str = 'grass'
    feature: str = ''


@dataclass
class Board:
    width: int
    height: int
    tiles: dict[Cell, Tile] = field(default_factory=dict)

    def contains(self, cell: Cell) -> bool:
        return 0 <= cell[0] < self.width and 0 <= cell[1] < self.height

    def tile(self, cell: Cell) -> Tile:
        return self.tiles.get(cell, Tile())

    def cells(self):
        for y in range(self.height):
            for x in range(self.width):
                yield x, y

    def neighbors(self, cell: Cell):
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            other = cell[0] + dx, cell[1] + dy
            if self.contains(other):
                yield other


@dataclass
class Effect:
    kind: str = "damage"
    power: int = 1
    element: str = "physical"
    status: str = ""
    duration: int = 24
    scope: str = "target"  # target / allies / enemies / all (relative to caster)


@dataclass
class Skill:
    id: str
    name: str
    effects: list[Effect]
    cost: int = 0
    range: int = 1
    min_range: int = 0
    radius: int = 0
    shape: str = "diamond"
    target: str = "enemy"  # enemy / ally / unit / self / ground / downed
    accuracy: int = 100
    magical: bool = False
    cast_ticks: int = 0
    lock: str = "cell"  # cell / unit
    los: bool = True
    optimal_range: int = 0
    falloff_per_tile: int = 0


@dataclass
class Unit:
    id: str
    name: str
    team: str
    pos: Cell
    footprint: tuple[int, int] = (1, 1)
    max_hp: int = 40
    hp: int = 40
    max_mp: int = 12
    mp: int = 12
    attack: int = 5
    magic: int = 6
    defense: int = 0
    magic_defense: int = 0
    speed: int = 10
    move: int = 4
    jump: int = 1
    weapon_power: int = 3
    weapon: str = "melee"
    attack_range: int = 1
    min_range: int = 1
    attack_range_mode: str = "fixed"  # fixed / los
    optimal_range: int = 0
    falloff_per_tile: int = 0
    engagement_range: int = -1  # -1 = infer from weapon family
    brave: int = 70
    faith: int = 60
    class_evade: int = 0
    shield_evade: int = 0
    accessory_evade: int = 0
    weapon_evade: int = 0
    magic_evade: int = 0
    reaction: str = "none"
    support: str = "none"
    movement: str = "none"
    facing: Cell = (0, 1)
    skills: list[str] = field(default_factory=list)
    tactics: list[str] = field(default_factory=list)
    resistances: dict[str, int] = field(default_factory=dict)
    statuses: dict[str, int] = field(default_factory=dict)
    ct: int = 0
    moved: bool = False
    acted: bool = False
    cast: dict | None = None
    disengaging: bool = False
    archetype: str = ""
    kind: str = "character"
    tags: list[str] = field(default_factory=list)
    behavior: str = "tactical"
    patrol_route: tuple[Cell, ...] = ()

    def occupied_cells(self, origin=None):
        x, y = self.pos if origin is None else origin
        width, height = self.footprint
        return {(x + dx, y + dy) for dy in range(height) for dx in range(width)}

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def movement_budget(self) -> int:
        """Legacy default-rule view; use Battle.movement_budget for composed rules."""
        return self.move + {"move_plus_1": 1, "move_plus_2": 2}.get(self.movement, 0)


@dataclass
class Mission:
    id: str
    name: str
    board: Board
    units: list[Unit]
    objective: str = "eliminate"
    target_ticks: int = 100
    goal: list[Cell] = field(default_factory=list)
    protected_id: str = ""
    objects: list[dict] = field(default_factory=list)
    triggers: list[dict] = field(default_factory=list)
    reward: int = 100
    next_missions: list[str] = field(default_factory=list)
    relic: Cell | None = None
    deployment: list[dict] = field(default_factory=list)
    # Optional, presentation-only authoring identity (absent in legacy JSON).
    structures: list[dict] = field(default_factory=list)
    # Optional visual upper decks; Battle remains strictly 2D in Content v1.
    interior_floors: list[dict] = field(default_factory=list)
    # Optional 3.7.20C tactical metadata, absent from all legacy missions.
    unit_levels: dict[str, int] = field(default_factory=dict)
    level_links: list[dict] = field(default_factory=list)
    # Mission-local editor hierarchy; ignored by Battle and tactical saves.
    editor_groups: list[dict] = field(default_factory=list)


@dataclass
class Content:
    skills: dict[str, Skill]
    missions: dict[str, Mission]
    jobs: dict[str, dict] = field(default_factory=dict)
    equipment: dict[str, dict] = field(default_factory=dict)
    tactic_unlocks: list[dict] = field(default_factory=list)
    archetypes: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict, *, rules=None) -> Content:
        try:
            require(data["version"] == 1, "Unsupported content version")
            from .actors import ActorFactory
            factory = ActorFactory(data.get('archetypes', {}))
            skills = {}
            for row in data["skills"]:
                s = Skill(**{**row, "effects": [Effect(**e) for e in row["effects"]]})
                require(s.id not in skills, f"Duplicate skill: {s.id}")
                skills[s.id] = s
            missions = {}
            for row in data["missions"]:
                raw_board = row["board"]
                tiles = {}
                for t in raw_board.get("tiles", []):
                    cell = tuple(t["pos"])
                    require(cell not in tiles, f"Duplicate tile: {cell}")
                    tiles[cell] = Tile(**{k: v for k, v in t.items() if k != "pos"})
                board = Board(raw_board["width"], raw_board["height"], tiles)
                units = [factory.create(u) for u in row["units"]]
                m = Mission(**{**row, "board": board, "units": units,
                               "relic": tuple(row["relic"]) if row.get("relic") is not None else None,
                               "goal": [tuple(c) for c in row.get("goal", [])]})
                require(m.id not in missions, f"Duplicate mission: {m.id}")
                missions[m.id] = m
            result = cls(skills, missions, data.get("jobs", {}), data.get("equipment", {}),
                         data.get("tactic_unlocks", []), data.get("archetypes", {}))
            result.validate(rules=rules)
            return result
        except (KeyError, TypeError, AttributeError) as exc:
            raise RuleError(f"Invalid content structure: {exc}") from exc

    @classmethod
    def load(cls, path: str | Path, *, rules=None) -> Content:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")), rules=rules)

    def to_dict(self) -> dict:
        missions = []
        for mission in self.missions.values():
            row = {k: v for k, v in asdict(mission).items()
                   if k != "board" and (k not in ("structures", "interior_floors",
                                               "unit_levels", "level_links", "editor_groups") or v)}
            row["board"] = {"width": mission.board.width, "height": mission.board.height,
                            "tiles": [{"pos": list(c), **asdict(t)} for c, t in sorted(mission.board.tiles.items())]}
            missions.append(row)
        return {"version": 1, "skills": [asdict(s) for s in self.skills.values()],
                "missions": missions, "jobs": self.jobs, "equipment": self.equipment,
                "tactic_unlocks": self.tactic_unlocks, "archetypes": self.archetypes}

    def validate(self, *, rules=None) -> None:
        from .rules import default_rules
        rules = rules if rules is not None else default_rules()
        def integer(value, low, high, label):
            require(type(value) is int and low <= value <= high, f"{label}: expected integer {low}..{high}")

        def cell(value, board):
            require(len(value) == 2 and all(type(v) is int for v in value) and board.contains(value),
                    f"Invalid cell: {value}")

        from .actors import ActorFactory, validate_actor
        factory = ActorFactory(self.archetypes)
        for key in self.archetypes:
            actor = factory.create({'id': 'template', 'name': key, 'team': 'player', 'pos': (0, 0), 'archetype': key})
            validate_actor(actor, self.skills, self.archetypes, rules)

        for s in self.skills.values():
            require(bool(s.id) and bool(s.effects), "Skill needs an id and effects")
            for key in ("cost", "range", "min_range", "radius", "cast_ticks", "optimal_range", "falloff_per_tile"):
                integer(getattr(s, key), 0, 100, f"{s.id}.{key}")
            integer(s.accuracy, 0, 100, f"{s.id}.accuracy")
            require(s.min_range <= s.range, f"{s.id}: invalid range")
            require(s.target in {"enemy", "ally", "unit", "self", "ground", "downed"}, f"{s.id}: target")
            require(s.shape in {"diamond", "cross", "square"}, f"{s.id}: shape")
            require(s.lock in {"cell", "unit"}, f"{s.id}: lock")
            require(s.target != "ground" or s.lock == "cell", f"{s.id}: ground requires cell lock")
            for e in s.effects:
                require(e.kind in rules.effects, f"{s.id}: effect")
                require(e.scope in {"target", "allies", "enemies", "all"}, f"{s.id}: scope")
                integer(e.power, 0, 10000, f"{s.id}.power")
                integer(e.duration, 1, 10000, f"{s.id}.duration")
                require(e.kind not in {"status", "cleanse"} or e.status in rules.statuses, f"{s.id}: unknown status")
        require(bool(self.missions), "At least one mission required")
        for m in self.missions.values():
            b = m.board
            integer(b.width, 1, 128, "width")
            integer(b.height, 1, 128, "height")
            integer(m.target_ticks, 1, 100000, "target_ticks")
            integer(m.reward, 0, 1000000, "reward")
            objective = rules.objectives.get(m.objective)
            require(not objective.needs_goal or bool(m.goal), "Objective needs goal cells")
            require(not objective.needs_relic or m.relic is not None, "Objective needs a relic")
            if m.relic is not None:
                cell(m.relic, b)
                require(not b.tile(m.relic).blocked, "Relic is blocked")
            for c in m.goal:
                cell(c, b)
                require(not b.tile(c).blocked, "Goal is blocked")
            from .terrain_schema import SURFACES, FEATURES
            for c, t in b.tiles.items():
                cell(c, b)
                integer(t.height, 0, 99, "tile.height")
                integer(t.cost, 1, 99, "tile.cost")
                integer(t.hazard, 0, 10000, "tile.hazard")
                integer(t.cover, 0, 100, "tile.cover")
                require(type(t.surface) is str and t.surface in SURFACES,
                        "Invalid tile surface")
                require(type(t.feature) is str and t.feature in FEATURES,
                        "Invalid tile feature")
            # Stored architecture is visual metadata; it never overrides tiles
            # or their tactical collision/height. A repainted wall is valid.
            from .iso_structures import structure_template, structure_footprint
            require(type(m.structures) is list, "Mission structures must be a list")
            structure_ids, structure_cells = set(), set()
            for structure in m.structures:
                require(type(structure) is dict and
                        set(structure) in (
                            {"id", "name", "anchor", "turns", "door_slot"},
                            {"id", "name", "anchor", "turns", "door_slot", "underlay"},
                            {"id", "name", "anchor", "turns", "door_slot", "appearance"},
                            {"id", "name", "anchor", "turns", "door_slot", "underlay", "appearance"}),
                        "Invalid structure metadata fields")
                from .building_visuals import validate_building_appearance
                validate_building_appearance(structure)
                sid = structure["id"]
                require(type(sid) is str and 1 <= len(sid) <= 64
                        and sid.isascii() and sid[0].isalpha()
                        and all(ch.isalnum() or ch in "_-" for ch in sid)
                        and sid not in structure_ids,
                        "Duplicate or invalid structure id")
                structure_ids.add(sid)
                clip = structure_template(structure["name"], structure["turns"],
                                          door_slot=structure["door_slot"])
                footprint = set(structure_footprint(clip, structure["anchor"]))
                require(all(b.contains(c) for c in footprint),
                        f"{sid}: structure outside map")
                require(not footprint.intersection(structure_cells),
                        f"{sid}: overlapping structures")
                # An optional record-local snapshot preserves the exact
                # sparse ground underneath new structures. Historical
                # records without underlay remain valid and unchanged.
                if "underlay" in structure:
                    underlay = structure["underlay"]
                    require(type(underlay) is list and
                            len(underlay) == len(footprint),
                            f"{sid}: invalid underlay size")
                    snapshot_cells = set()
                    for entry in underlay:
                        require(type(entry) is dict and
                                set(entry) == {"pos", "tile"} and
                                type(entry["pos"]) is list and
                                len(entry["pos"]) == 2 and
                                all(type(n) is int for n in entry["pos"]),
                                f"{sid}: invalid underlay cell")
                        position = tuple(entry["pos"])
                        require(position in footprint and
                                position not in snapshot_cells,
                                f"{sid}: invalid underlay footprint")
                        snapshot_cells.add(position)
                        raw = entry["tile"]
                        if raw is not None:
                            require(type(raw) is dict and
                                    set(raw) == set(asdict(Tile())),
                                    f"{sid}: invalid underlay tile")
                            require(type(raw["blocked"]) is bool and
                                    type(raw["height"]) is int and
                                    0 <= raw["height"] <= 99 and
                                    type(raw["cost"]) is int and
                                    1 <= raw["cost"] <= 99 and
                                    type(raw["cover"]) is int and
                                    0 <= raw["cover"] <= 100 and
                                    type(raw["hazard"]) is int and
                                    0 <= raw["hazard"] <= 10000 and
                                    type(raw["surface"]) is str and
                                    raw["surface"] in SURFACES and
                                    type(raw["feature"]) is str and
                                    raw["feature"] in FEATURES,
                                    f"{sid}: invalid underlay terrain")
                    require(snapshot_cells == footprint,
                            f"{sid}: incomplete underlay footprint")
                structure_cells.update(footprint)
            from .interior_levels import validate_interior_floors
            validate_interior_floors(m.interior_floors, m.structures)
            from .level_navigation import validate_levels, walkable_levels
            level_cells = validate_levels(m)
            ids, occupied = set(), set()
            for u in m.units:
                require(u.id and u.id not in ids, f"Duplicate/empty unit: {u.id}")
                ids.add(u.id)
                require(isinstance(u.footprint, (tuple, list)) and len(u.footprint) == 2
                        and all(type(n) is int and 1 <= n <= 4 for n in u.footprint),
                        f"Invalid footprint: {u.id}")
                cells = u.occupied_cells()
                level = m.unit_levels.get(u.id, 0)
                require(all(c in level_cells.get(level, set())
                            and (level, *c) not in occupied
                            for c in cells), f"Invalid spawn: {u.id}")
                occupied.update((level, *c) for c in cells)
                validate_actor(u, self.skills, self.archetypes, rules)
                for waypoint in u.patrol_route:
                    cell(waypoint, b)
                    require(not b.tile(waypoint).blocked,
                            f"{u.id}: patrol waypoint is blocked")
            require(any(u.team == "player" for u in m.units), "Mission needs a player")
            require(any(u.team == "enemy" for u in m.units), "Mission needs an enemy")
            require(not m.protected_id or m.protected_id in ids, "Unknown protected unit")
            if m.objective in {"escort", "defend"}:
                require(m.protected_id and any(
                    unit.id == m.protected_id and unit.team == "player"
                    for unit in m.units), "Objective needs a protected player unit")
            if m.objective == "sabotage":
                require(any(obj["kind"] == "defense" and obj.get("team") == "enemy"
                            for obj in m.objects), "Sabotage needs an enemy defense")
            require(all(n in self.missions for n in m.next_missions), "Unknown next mission")
            from .deployment import validate as validate_deployment
            validate_deployment(m)
            object_ids = set()
            for obj in m.objects:
                require(obj["id"] not in object_ids, "Duplicate object")
                object_ids.add(obj["id"])
                cell(obj["pos"], b)
                require(obj["kind"] in {"door", "switch", "chest", "ram", "catapult", "passage", "defense"}, "Unknown object kind")
                from .siege import validate as validate_siege
                validate_siege(m, obj, cell, integer)
                integer(obj.get("amount", 1), 0, 10000, "object.amount")
                if obj["kind"] == "door":
                    integer(obj.get("hp", 1), 1, 10000, "door.hp")
                    require(type(obj.get("locked", False)) is bool, "door.locked must be boolean")
                if obj["kind"] in {"ram", "catapult"}:
                    integer(obj.get("power", 1), 1, 10000, "siege.power")
                    require(obj.get("team", "player") in {"player", "enemy"}, "Invalid siege engine team")
                    maximum = obj.get("max_hp", obj.get("hp", 12))
                    integer(maximum, 1, 10000, "siege.max_hp")
                    integer(obj.get("hp", maximum), 1, maximum, "siege.hp")
                    if obj["kind"] == "catapult" and "ammo" in obj:
                        integer(obj["ammo"], 0, 10000, "catapult.ammo")
                    integer(obj.get("repair", 8), 1, 10000, "siege.repair")
                    integer(obj.get("repair_charges", 0), 0, 100, "siege.repair_charges")
                    require(obj.get("link") != obj["id"], "Siege engine cannot target itself")
            for obj in m.objects:
                require(obj["kind"] != "switch" or any(o["id"] == obj.get("link") and o["kind"] == "door" for o in m.objects), "Switch needs a door")
                require(obj["kind"] != "door" or tuple(obj["pos"]) not in occupied, "Door on spawn")
            for obj in m.objects:
                if obj["kind"] in {"ram", "catapult"}:
                    require(any(o["id"] == obj.get("link") and o["kind"] == "door" for o in m.objects),
                            "Siege engine needs a gate target")
            # Chained events use ordinary Mission.triggers and stored event IDs;
            # validate the complete graph before allowing any Player load.
            if any('after' in t or 'after_any' in t for t in m.triggers):
                require(len(m.triggers) <= 200,
                        "Event chain budget exceeded (200 triggers)")
                dependencies = {}
                known = {t['id'] for t in m.triggers}
                for row in m.triggers:
                    refs = []
                    for field in ('after', 'after_any'):
                        group = row.get(field, [])
                        if field in row:
                            require(isinstance(group, list) and
                                    1 <= len(group) <= 8,
                                    'Event ' + field + ' requires 1..8 entries')
                        require(isinstance(group, list),
                                'Event prerequisites must be lists')
                        refs += group
                    require(all(isinstance(ref, str) and ref in known
                                and ref != row['id'] for ref in refs)
                            and len(refs) == len(set(refs)),
                            "Unknown, self-referential or duplicate event prerequisite")
                    dependencies[row['id']] = set(refs)
                remaining = {key: set(refs) for key, refs in dependencies.items()}
                while remaining:
                    ready = set(key for key, refs in remaining.items() if not refs)
                    require(bool(ready), "Cyclic tactical event dependency")
                    remaining = {key: refs - ready for key, refs in
                                 remaining.items() if key not in ready}
            # Optional timed gates use the canonical trigger journal; no queue.
            known_trigger_ids = {row['id'] for row in m.triggers}
            for row in m.triggers:
                delayed = False
                for key in ('delay_ticks', 'delay_activations',
                            'expire_after_ticks', 'expire_after_activations'):
                    if key in row:
                        require(type(row[key]) is int and 1 <= row[key] <= 10000,
                                f'{key} must be 1..10000')
                        delayed = True
                if delayed:
                    require(bool(row.get('after') or row.get('after_any')),
                            'Timed trigger requires a predecessor')
                    require(len(m.triggers) <= 200,
                            'Temporal event budget exceeded (200 triggers)')
                for unit in ('ticks', 'activations'):
                    delay = row.get('delay_' + unit, 0)
                    expires = row.get('expire_after_' + unit)
                    if expires is not None:
                        require(expires > delay,
                                'Expiration must follow its corresponding delay')
                if 'cancel_after' in row:
                    refs = row['cancel_after']
                    require(isinstance(refs, list) and 1 <= len(refs) <= 8,
                            'Cancellation requires 1..8 event IDs')
                    require(all(type(ref) is str and ref in known_trigger_ids
                                and ref != row['id'] for ref in refs)
                            and len(refs) == len(set(refs)),
                            'Invalid cancellation reference')
            trigger_ids = set()
            for trigger in m.triggers:
                require(trigger["id"] not in trigger_ids, "Duplicate trigger")
                trigger_ids.add(trigger["id"])
                from .rules.triggers import ValidationContext
                context = ValidationContext(b, ids, rules, self.archetypes, object_ids)
                if 'after_choice' in trigger:
                    choice = trigger['after_choice']
                    require(isinstance(choice, dict)
                            and set(choice) == {'scene', 'choice'}
                            and all(isinstance(choice.get(key), str)
                                    and 0 < len(choice[key]) <= 64
                                    for key in ('scene', 'choice')),
                            'Invalid tactical choice event guard')
                rules.trigger_conditions.get(trigger['condition']).validate(context, trigger)
                if 'when' in trigger:
                    from .rules.triggers import validate_composite
                    validate_composite(context, trigger['when'])
                for action in trigger['actions']:
                    rules.trigger_actions.get(action['kind']).validate(context, action)
            # Extra event pages are opt-in, but use the SAME rule registries
            # and cross-reference tables as existing Mission.triggers.
            from .rules.triggers import ValidationContext
            from .event_pages import validate_pages
            validate_pages(m, ValidationContext(
                b, ids, rules, self.archetypes, object_ids), rules)
            from .editor_groups import validate_editor_groups
            validate_editor_groups(m)
        def unlock_rule(rule):
            require(isinstance(rule, dict), "Tactic unlock rule must be an object")
            if "all" in rule or "any" in rule:
                key = "all" if "all" in rule else "any"
                require(isinstance(rule[key], list) and bool(rule[key]), f"Tactic unlock {key} must be non-empty")
                for child in rule[key]:
                    unlock_rule(child)
                return
            if "stat" in rule:
                require(isinstance(rule["stat"], str) and bool(rule["stat"]), "Invalid tactic unlock stat")
                integer(rule.get("gte", 1), 1, 1000000, "tactic unlock gte")
                return
            if "mission" in rule:
                require(rule["mission"] in self.missions, "Unknown tactic unlock mission")
                return
            if "completed_mission" in rule:
                require(rule["completed_mission"] in self.missions, "Unknown completed tactic mission")
                return
            if "sequence" in rule:
                require(isinstance(rule["sequence"], list) and bool(rule["sequence"]), "Empty tactic sequence")
                require(all(isinstance(spec, (str, dict)) for spec in rule["sequence"]), "Invalid tactic sequence event")
                if "max_ticks" in rule:
                    integer(rule["max_ticks"], 1, 100000, "tactic sequence max_ticks")
                integer(rule.get("count", 1), 1, 1000, "tactic sequence count")
                require(type(rule.get("same_target", False)) is bool, "Invalid same_target")
                require(rule.get("require_sources") in {None, "all_members"}, "Invalid sequence source rule")
                return
            raise RuleError("Unknown tactic unlock rule")

        all_unit_ids = {u.id for m in self.missions.values() for u in m.units if u.team == "player"}
        for rule in self.tactic_unlocks:
            tactic = rule.get("id")
            require(tactic in rules.tactics, "Unknown tactic unlock id")
            members = rule.get("members", [])
            require(isinstance(members, list) and len(members) in {2, 3}
                    and len(set(members)) == len(members),
                    "Tactic unlock needs two or three distinct members")
            require(len(members) == rules.tactics.get(tactic).arity, "Tactic unlock arity mismatch")
            require(all(member in all_unit_ids for member in members), "Unknown tactic unlock member")
            hints = rule.get("hints", {})
            require(isinstance(hints, dict) and set(hints) <= {"hidden", "clue", "near", "unlocked"}
                    and all(isinstance(value, str) and bool(value) for value in hints.values()),
                    "Invalid tactic unlock hints")
            unlock_rule(rule.get("unlock"))

        for jid, job in self.jobs.items():
            require(job.get("requires", "") in {"", *self.jobs}, f"{jid}: prerequisite job")
            integer(job.get("requires_level", 1), 1, 20, "requires_level")
            require(all(s in self.skills for s in job.get("skills", {})), f"{jid}: unknown skill")
            for level in job.get("skills", {}).values():
                integer(level, 1, 20, "skill level")
            require(set(job.get("bonuses", {})) <= {"max_hp", "max_mp", "attack", "magic", "defense", "magic_defense", "move", "speed"}, "Unknown job bonus")
            for bonus in job.get("bonuses", {}).values():
                integer(bonus, 0, 100, "job bonus")
        from .builds3 import validate_talent_trees
        validate_talent_trees(self)
        for item in self.equipment.values():
            integer(item.get("price", 0), 0, 1000000, "equipment price")
            require(item["slot"] in {"weapon", "armor", "accessory"}, "Unknown equipment slot")
            require(set(item.get("bonuses", {})) <= {"max_hp", "max_mp", "attack", "magic", "defense", "magic_defense", "move", "speed", "weapon_power"}, "Unknown equipment bonus")
            for bonus in item.get("bonuses", {}).values():
                integer(bonus, 0, 100, "equipment bonus")

