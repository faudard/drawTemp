"""Persistent roster, jobs, equipment and once-only mission rewards."""
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path

from .engine import Battle
from .model import Content, require
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

    def hero(self, uid):
        return self.heroes.setdefault(uid, HeroProgress())

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

    def prepare(self, content, mission_id, seed=1):
        require(mission_id in self.unlocked, "Mission locked")
        prepared = deepcopy(content)
        for unit in prepared.missions[mission_id].units:
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
        prepared.validate()
        return Battle(prepared, mission_id, seed)

    def finish(self, battle, playtest=False):
        if playtest or battle.result != "victory" or battle.mission.id in self.completed:
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
        return True

    def save(self, path):
        write_json(path, {"version": 1, **asdict(self)})

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        require(data.pop("version", None) == 1, "Unsupported campaign version")
        data["heroes"] = {uid: HeroProgress(**p) for uid, p in data["heroes"].items()}
        result = cls(**data)
        require(type(result.gold) is int and result.gold >= 0, "Invalid gold")
        require(all(type(n) is int and n >= 0 for n in result.inventory.values()), "Invalid inventory")
        for h in result.heroes.values():
            require(type(h.xp) is int and h.xp >= 0 and all(type(n) is int and n >= 0 for n in h.job_xp.values()), "Invalid XP")
        return result
