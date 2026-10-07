"""Typed content contracts shared by simulation, CLI and the editor."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path

Cell = tuple[int, int]
STATUSES = {"poison", "regen", "haste", "slow", "protect", "shell", "silence",
            "sleep", "stop", "dont_move", "dont_act", "guard"}
REACTIONS = {"none", "counter", "opportunity", "pursuit", "blade_grasp", "auto_potion", "mp_switch"}
TEAM_TACTICS = {"pincer", "crossfire", "encirclement"}\nTEAM_TACTIC_ARITY = {"pincer": 2, "crossfire": 2, "encirclement": 3}
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

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def movement_budget(self) -> int:
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


@dataclass
class Content:
    skills: dict[str, Skill]
    missions: dict[str, Mission]
    jobs: dict[str, dict] = field(default_factory=dict)
    equipment: dict[str, dict] = field(default_factory=dict)
    tactic_unlocks: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Content:
        try:
            require(data["version"] == 1, "Unsupported content version")
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
                units = []
                for u in row["units"]:
                    values = {**u, "pos": tuple(u["pos"]), "facing": tuple(u.get("facing", [0, 1]))}
                    values.setdefault("hp", u.get("max_hp", 40))
                    values.setdefault("mp", u.get("max_mp", 12))
                    units.append(Unit(**values))
                m = Mission(**{**row, "board": board, "units": units,
                               "relic": tuple(row["relic"]) if row.get("relic") is not None else None,
                               "goal": [tuple(c) for c in row.get("goal", [])]})
                require(m.id not in missions, f"Duplicate mission: {m.id}")
                missions[m.id] = m
            result = cls(skills, missions, data.get("jobs", {}), data.get("equipment", {}),
                         data.get("tactic_unlocks", []))
            result.validate()
            return result
        except (KeyError, TypeError, AttributeError) as exc:
            raise RuleError(f"Invalid content structure: {exc}") from exc

    @classmethod
    def load(cls, path: str | Path) -> Content:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict:
        missions = []
        for mission in self.missions.values():
            row = {k: v for k, v in asdict(mission).items() if k != "board"}
            row["board"] = {"width": mission.board.width, "height": mission.board.height,
                            "tiles": [{"pos": list(c), **asdict(t)} for c, t in sorted(mission.board.tiles.items())]}
            missions.append(row)
        return {"version": 1, "skills": [asdict(s) for s in self.skills.values()],
                "missions": missions, "jobs": self.jobs, "equipment": self.equipment,
                "tactic_unlocks": self.tactic_unlocks}

    def validate(self) -> None:
        def integer(value, low, high, label):
            require(type(value) is int and low <= value <= high, f"{label}: expected integer {low}..{high}")

        def cell(value, board):
            require(len(value) == 2 and all(type(v) is int for v in value) and board.contains(value),
                    f"Invalid cell: {value}")

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
                require(e.kind in {"damage", "heal", "revive", "status", "cleanse", "push", "pull", "mp", "zone"}, f"{s.id}: effect")
                require(e.scope in {"target", "allies", "enemies", "all"}, f"{s.id}: scope")
                integer(e.power, 0, 10000, f"{s.id}.power")
                integer(e.duration, 1, 10000, f"{s.id}.duration")
                require(e.kind not in {"status", "cleanse"} or e.status in STATUSES, f"{s.id}: unknown status")
        require(bool(self.missions), "At least one mission required")
        for m in self.missions.values():
            b = m.board
            integer(b.width, 1, 128, "width")
            integer(b.height, 1, 128, "height")
            integer(m.target_ticks, 1, 100000, "target_ticks")
            integer(m.reward, 0, 1000000, "reward")
            require(m.objective in {"eliminate", "survive", "extract", "hold", "crown"}, "Unknown objective")
            require(m.objective not in {"extract", "hold", "crown"} or bool(m.goal), "Objective needs goal cells")
            require(m.objective != "crown" or m.relic is not None, "Crown objective needs a relic")
            if m.relic is not None:
                cell(m.relic, b)
                require(not b.tile(m.relic).blocked, "Relic is blocked")
            for c in m.goal:
                cell(c, b)
                require(not b.tile(c).blocked, "Goal is blocked")
            for c, t in b.tiles.items():
                cell(c, b)
                integer(t.height, 0, 99, "tile.height")
                integer(t.cost, 1, 99, "tile.cost")
                integer(t.hazard, 0, 10000, "tile.hazard")
                integer(t.cover, 0, 100, "tile.cover")
            ids, occupied = set(), set()
            for u in m.units:
                require(u.id and u.id not in ids, f"Duplicate/empty unit: {u.id}")
                ids.add(u.id)
                cell(u.pos, b)
                require(u.pos not in occupied and not b.tile(u.pos).blocked, f"Invalid spawn: {u.id}")
                occupied.add(u.pos)
                require(u.team in {"player", "enemy"}, f"{u.id}: team")
                for key in ("max_hp", "speed", "weapon_power", "attack_range"):
                    integer(getattr(u, key), 1, 10000, f"{u.id}.{key}")
                for key in ("max_mp", "attack", "magic", "defense", "magic_defense", "move", "jump", "min_range"):
                    integer(getattr(u, key), 0, 10000, f"{u.id}.{key}")
                integer(u.hp, 1, u.max_hp, f"{u.id}.hp")
                integer(u.mp, 0, u.max_mp, f"{u.id}.mp")
                integer(u.ct, 0, 10000, f"{u.id}.ct")
                for key in ("brave", "faith", "class_evade", "shield_evade", "accessory_evade", "weapon_evade", "magic_evade"):
                    integer(getattr(u, key), 0, 100, f"{u.id}.{key}")
                require(u.min_range <= u.attack_range, f"{u.id}: range")
                require(u.attack_range_mode in {"fixed", "los"}, f"{u.id}: attack_range_mode")
                integer(u.optimal_range, 0, 10000, f"{u.id}.optimal_range")
                integer(u.falloff_per_tile, 0, 100, f"{u.id}.falloff_per_tile")
                integer(u.engagement_range, -1, 8, f"{u.id}.engagement_range")
                require(all(t in TEAM_TACTICS for t in u.tactics), f"{u.id}: unknown tactic")
                require(u.weapon in {"melee", "spear", "ranged", "focus", "unarmed"}, f"{u.id}: weapon")
                require(u.facing in {(0, 1), (0, -1), (1, 0), (-1, 0)}, f"{u.id}: facing")
                require(u.reaction in REACTIONS and u.support in SUPPORTS and u.movement in MOVEMENTS, f"{u.id}: ability slot")
                require(all(s in self.skills for s in u.skills), f"{u.id}: unknown skill")
                require(u.cast is None and not u.moved and not u.acted and not u.disengaging, "Mission spawns cannot be mid-turn")
                for status, duration in u.statuses.items():
                    require(status in STATUSES, f"{u.id}: status")
                    integer(duration, -1, 10000, f"{u.id}.status duration")
                    require(duration != 0, "Status duration must not be zero")
                for resistance in u.resistances.values():
                    integer(resistance, -100, 100, "resistance")
            require(any(u.team == "player" for u in m.units), "Mission needs a player")
            require(any(u.team == "enemy" for u in m.units), "Mission needs an enemy")
            require(not m.protected_id or m.protected_id in ids, "Unknown protected unit")
            require(all(n in self.missions for n in m.next_missions), "Unknown next mission")
            object_ids = set()
            for obj in m.objects:
                require(obj["id"] not in object_ids, "Duplicate object")
                object_ids.add(obj["id"])
                cell(obj["pos"], b)
                require(obj["kind"] in {"door", "switch", "chest"}, "Unknown object kind")
                integer(obj.get("amount", 1), 0, 10000, "object.amount")
            for obj in m.objects:
                require(obj["kind"] != "switch" or any(o["id"] == obj.get("link") and o["kind"] == "door" for o in m.objects), "Switch needs a door")
                require(obj["kind"] != "door" or tuple(obj["pos"]) not in occupied, "Door on spawn")
            trigger_ids = set()
            for trigger in m.triggers:
                require(trigger["id"] not in trigger_ids, "Duplicate trigger")
                trigger_ids.add(trigger["id"])
                require(trigger["condition"] in {"tick", "enter", "defeated"}, "Unknown trigger condition")
                if trigger["condition"] == "tick":
                    integer(trigger["value"], 0, 100000, "trigger tick")
                elif trigger["condition"] == "enter":
                    cell(trigger["pos"], b)
                else:
                    require(trigger["unit"] in ids, "Unknown trigger unit")
                for action in trigger["actions"]:
                    require(action["kind"] in {"hazard", "message", "status"}, "Unknown trigger action")
                    if action["kind"] == "hazard":
                        cell(action["pos"], b)
                        integer(action["amount"], 0, 10000, "trigger hazard")
                    elif action["kind"] == "status":
                        require(action["unit"] in ids and action["status"] in STATUSES, "Invalid trigger status")
                        integer(action["duration"], 1, 10000, "trigger duration")
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
            require(tactic in TEAM_TACTICS, "Unknown tactic unlock id")
            members = rule.get("members", [])
            require(isinstance(members, list) and len(members) in {2, 3}
                    and len(set(members)) == len(members),
                    "Tactic unlock needs two or three distinct members")
            require(len(members) == TEAM_TACTIC_ARITY[tactic], "Tactic unlock arity mismatch")
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
        for item in self.equipment.values():
            integer(item.get("price", 0), 0, 1000000, "equipment price")
            require(item["slot"] in {"weapon", "armor", "accessory"}, "Unknown equipment slot")
            require(set(item.get("bonuses", {})) <= {"max_hp", "max_mp", "attack", "magic", "defense", "magic_defense", "move", "speed", "weapon_power"}, "Unknown equipment bonus")
            for bonus in item.get("bonuses", {}).values():
                integer(bonus, 0, 100, "equipment bonus")
