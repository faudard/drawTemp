"""Persistent roster, jobs, equipment and once-only mission rewards."""
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path

from .bonds import (battle_bond_deltas, group_key, merge_bond_stats, pair_key,
                    unlock_progress, unlock_rule_met)
from .engine import Battle
from .model import Content, require
from .rules import default_rules
from .storage import write_json


@dataclass
class HeroProgress:
    xp: int = 0
    job: str = "brave"
    job_xp: dict[str, int] = field(default_factory=dict)
    equipment: dict[str, str] = field(default_factory=dict)

    @property
    def level(self):
        return min(20, 1 + self.xp // 100)

    def job_level(self, job):
        return min(20, 1 + self.job_xp.get(job, 0) // 50)


@dataclass
class Campaign:
    unlocked: list[str]
    heroes: dict[str, HeroProgress] = field(default_factory=dict)
    completed: list[str] = field(default_factory=list)
    gold: int = 0
    inventory: dict[str, int] = field(default_factory=dict)
    bond_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    known_tactics: dict[str, list[str]] = field(default_factory=dict)
    prepared_tactics: dict[str, list[str]] = field(default_factory=dict)
    tracked_battles: list[str] = field(default_factory=list)

    def hero(self, uid):
        return self.heroes.setdefault(uid, HeroProgress())

    def bond_group(self, *members):
        return self.bond_stats.setdefault(group_key(members), {})

    def bond(self, a, b):
        return self.bond_group(a, b)

    def record_bonds(self, battle):
        if battle.result not in {"victory", "defeat"} or battle.battle_id in self.tracked_battles:
            return False
        merge_bond_stats(self.bond_stats, battle_bond_deltas(battle))
        self.tracked_battles.append(battle.battle_id)
        return True

    def unlock_tactic_members(self, members, tactic, *, ruleset=None):
        ruleset = ruleset or default_rules()
        members = tuple(members)
        require(tactic in ruleset.tactics, "Tactic not implemented")
        require(len(members) == ruleset.tactics.get(tactic).arity, "Tactic member count mismatch")
        key = group_key(members)
        known = self.known_tactics.setdefault(key, [])
        if tactic in known:
            return False
        known.append(tactic)
        return True

    def unlock_tactic(self, a, b, tactic, *, ruleset=None):
        return self.unlock_tactic_members((a, b), tactic, ruleset=ruleset)

    def prepare_tactic_members(self, members, tactic, limit=2, *, ruleset=None):
        ruleset = ruleset or default_rules()
        members = tuple(members)
        require(tactic in ruleset.tactics, "Tactic not implemented")
        require(len(members) == ruleset.tactics.get(tactic).arity, "Tactic member count mismatch")
        key = group_key(members)
        require(tactic in self.known_tactics.get(key, []), "Tactic not unlocked")
        prepared = self.prepared_tactics.setdefault(key, [])
        if tactic in prepared:
            return False
        require(len(prepared) < limit, "Tactic preparation limit reached")
        prepared.append(tactic)
        return True

    def prepare_tactic(self, a, b, tactic, limit=2, *, ruleset=None):
        return self.prepare_tactic_members((a, b), tactic, limit, ruleset=ruleset)

    def unprepare_tactic_members(self, members, tactic):
        key = group_key(members)
        prepared = self.prepared_tactics.get(key, [])
        require(tactic in prepared, "Tactic not prepared")
        prepared.remove(tactic)
        return True

    def unprepare_tactic(self, a, b, tactic):
        return self.unprepare_tactic_members((a, b), tactic)

    def evaluate_tactic_unlocks(self, rules, mission_id="", events=None, *, ruleset=None):
        ruleset = ruleset or default_rules()
        unlocked = []
        completed = set(self.completed)
        for rule in rules:
            members = rule.get("members", [])
            tactic = rule["id"]
            require(tactic in ruleset.tactics, "Tactic not implemented")
            require(len(members) in {2, 3} and len(members) == ruleset.tactics.get(tactic).arity,
                    "Tactic unlock member count mismatch")
            key = group_key(members)
            if tactic in self.known_tactics.get(key, []):
                continue
            if unlock_rule_met(self.bond_stats.get(key, {}), rule["unlock"],
                               mission_id=mission_id, completed=completed,
                               events=events or [], members=members):
                self.known_tactics.setdefault(key, []).append(tactic)
                unlocked.append({"id": tactic, "members": list(members)})
        return unlocked

    def tactic_codex(self, rules, mission_id="", events=None):
        """Read-only progressive discovery view for UI/editor surfaces."""
        rows = []
        completed = set(self.completed)
        for rule in rules:
            members = rule.get("members", [])
            tactic = rule["id"]
            key = group_key(members)
            unlocked = tactic in self.known_tactics.get(key, [])
            progress = 1.0 if unlocked else unlock_progress(
                self.bond_stats.get(key, {}), rule["unlock"], mission_id=mission_id,
                completed=completed, events=events or [], members=members)
            state = ("unlocked" if unlocked else "near" if progress >= .75
                     else "clue" if progress > 0 else "hidden")
            rows.append({"id": tactic, "members": list(members), "state": state,
                         "progress": round(progress, 3),
                         "hint": rule.get("hints", {}).get(state, "")})
        return rows

    def set_job(self, content, uid, job):
        require(job in content.jobs, "Unknown job")
        hero = self.hero(uid)
        prereq = content.jobs[job].get("requires")
        require(not prereq or hero.job_level(prereq) >= content.jobs[job].get("requires_level", 1), "Job locked")
        hero.job = job

    def equip(self, content, uid, item_id):
        require(item_id in content.equipment and self.inventory.get(item_id, 0) > 0, "Item not owned")
        hero = self.hero(uid)
        slot = content.equipment[item_id]["slot"]
        previous = hero.equipment.get(slot)
        if previous:
            self.inventory[previous] = self.inventory.get(previous, 0) + 1
        self.inventory[item_id] -= 1
        hero.equipment[slot] = item_id

    def unequip(self, uid, slot):
        hero = self.hero(uid)
        require(slot in hero.equipment, "Slot is empty")
        item = hero.equipment.pop(slot)
        self.inventory[item] = self.inventory.get(item, 0) + 1

    def buy(self, content, item_id):
        require(item_id in content.equipment, "Unknown item")
        price = content.equipment[item_id].get("price", 0)
        require(price > 0 and self.gold >= price, "Item unavailable or insufficient gold")
        self.gold -= price
        self.inventory[item_id] = self.inventory.get(item_id, 0) + 1

    def prepare(self, content, mission_id, seed=1, *, ruleset=None):
        ruleset = ruleset or default_rules()
        require(mission_id in self.unlocked, "Mission locked")
        prepared = deepcopy(content)
        mission_units = prepared.missions[mission_id].units
        for unit in mission_units:
            if unit.team != "player":
                continue
            hero = self.hero(unit.id)
            unit.max_hp += (hero.level - 1) * 3
            unit.attack += (hero.level - 1) // 3
            job = content.jobs.get(hero.job, {})
            for key, value in job.get("bonuses", {}).items():
                setattr(unit, key, getattr(unit, key) + value)
            for sid, level in job.get("skills", {}).items():
                if hero.job_level(hero.job) >= level and sid not in unit.skills:
                    unit.skills.append(sid)
            for item_id in hero.equipment.values():
                require(item_id in content.equipment, "Unknown equipped item")
                for key, value in content.equipment[item_id].get("bonuses", {}).items():
                    setattr(unit, key, getattr(unit, key) + value)
            unit.hp, unit.mp = unit.max_hp, unit.max_mp
        by_id = {unit.id: unit for unit in mission_units if unit.team == "player"}
        for key, tactics in self.prepared_tactics.items():
            members = key.split("|")
            if not all(member in by_id for member in members):
                continue
            for tactic in tactics:
                require(tactic in self.known_tactics.get(key, []), "Prepared tactic is not unlocked")
                require(len(members) == ruleset.tactics.get(tactic).arity, "Prepared tactic member count mismatch")
                for member in members:
                    if tactic not in by_id[member].tactics:
                        by_id[member].tactics.append(tactic)
        prepared.validate(rules=ruleset)
        return Battle(prepared, mission_id, seed, rules=ruleset)

    def finish(self, battle, playtest=False, tactic_rules=None):
        if playtest or battle.result not in {"victory", "defeat"}:
            return False
        rules = battle.content.tactic_unlocks if tactic_rules is None else tactic_rules
        self.record_bonds(battle)
        if battle.result != "victory" or battle.mission.id in self.completed:
            if rules:
                self.evaluate_tactic_unlocks(rules, battle.mission.id, battle.events, ruleset=battle.rules)
            return False
        require(battle.mission.id in self.unlocked, "Mission was not unlocked")
        self.completed.append(battle.mission.id)
        self.gold += battle.mission.reward + battle.loot
        for unit in battle.units:
            if unit.team == "player":
                hero = self.hero(unit.id)
                hero.xp += 100
                hero.job_xp[hero.job] = hero.job_xp.get(hero.job, 0) + 50
        for mission in battle.mission.next_missions:
            if mission not in self.unlocked:
                self.unlocked.append(mission)
        if rules:
            self.evaluate_tactic_unlocks(rules, battle.mission.id, battle.events, ruleset=battle.rules)
        return True

    def save(self, path):
        write_json(path, {"version": 1, **asdict(self)})

    @classmethod
    def load(cls, path, *, ruleset=None):
        ruleset = ruleset or default_rules()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        require(data.pop("version", None) == 1, "Unsupported campaign version")
        data["heroes"] = {uid: HeroProgress(**p) for uid, p in data["heroes"].items()}
        result = cls(**data)
        require(type(result.gold) is int and result.gold >= 0, "Invalid gold")
        require(all(type(n) is int and n >= 0 for n in result.inventory.values()), "Invalid inventory")
        require(all(isinstance(k, str) and all(type(v) is int and v >= 0 for v in stats.values())
                    for k, stats in result.bond_stats.items()), "Invalid bond stats")
        def tactic_key_valid(key, tactics):
            members = key.split("|")
            return (len(members) in {2, 3} and len(set(members)) == len(members)
                    and members == sorted(members)
                    and all(t in ruleset.tactics and ruleset.tactics.get(t).arity == len(members)
                            for t in tactics))
        require(all(isinstance(k, str) and isinstance(v, list) and tactic_key_valid(k, v)
                    for k, v in result.known_tactics.items()), "Invalid known tactics")
        require(all(isinstance(k, str) and isinstance(v, list) and len(v) <= 2
                    and len(v) == len(set(v)) and tactic_key_valid(k, v)
                    and all(t in result.known_tactics.get(k, []) for t in v)
                    for k, v in result.prepared_tactics.items()), "Invalid prepared tactics")
        require(len(result.tracked_battles) == len(set(result.tracked_battles))
                and all(isinstance(b, str) for b in result.tracked_battles), "Invalid tracked battles")
        for h in result.heroes.values():
            require(type(h.xp) is int and h.xp >= 0 and all(type(n) is int and n >= 0 for n in h.job_xp.values()), "Invalid XP")
        return result
