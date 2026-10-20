"""R41.B2 — small deterministic RPG_TURN encounter adapter.

This is *not* tactical Battle and does not alter CT. Actors and skills come
only from canonical Content; items/rewards belong to Campaign/GameSession.
The bounded command journal is replayed when loading a GameSession checkpoint.
"""
from __future__ import annotations

from copy import deepcopy

from .classic_party import rpg_turn_order
from .game_modes import resolve_scene_profile
from .model import require

VERSION = 1
MAX_COMMANDS = 256


def validate_encounters(raw, *, content, project):
    """Optional authored encounters inside the versioned R41 project extension."""
    require(type(raw) is dict and len(raw) <= 64, "Invalid R41 encounter catalogue")
    enemies = {u.id for mission in content.missions.values()
               for u in mission.units if u.team == "enemy"}
    for eid, row in raw.items():
        require(type(eid) is str and 1 <= len(eid) <= 48
                and all(c.isalnum() or c in "_-" for c in eid),
                "Invalid encounter ID")
        require(type(row) is dict and set(row) ==
                {"scene", "enemies", "reward_gold"},
                "Encounter needs scene, enemies and reward_gold")
        require(type(row["scene"]) is str
                and row["scene"] in project.exploration
                and resolve_scene_profile(project.game_modes,
                                          row["scene"])["combat"] == "RPG_TURN",
                "R41 encounter needs an existing RPG_TURN exploration scene")
        mobs = row["enemies"]
        require(type(mobs) is list and 1 <= len(mobs) <= 12
                and all(type(uid) is str and uid in enemies for uid in mobs)
                and len(set(mobs)) == len(mobs),
                "Encounter enemies must reference distinct canonical enemies")
        require(type(row["reward_gold"]) is int
                and 0 <= row["reward_gold"] <= 10000,
                "Invalid R41 encounter gold reward")
    return deepcopy(raw)


def _source_units(content, team):
    units = {}
    for mission in content.missions.values():
        for unit in mission.units:
            if unit.team == team:
                units.setdefault(unit.id, unit)
    return units


class ClassicEncounter:
    """Bounded, pure-command battle state owned by GameSession.

    Inputs: attack, guard, skill, item/potion or flee. Enemies automatically
    choose the weakest remaining party member (ID tie-break). No RNG or timer.
    """
    def __init__(self, encounter_id, config, party, content, inventory,
                 hero_progress=None):
        self.id = encounter_id
        self.scene = config["scene"]
        self.reward_gold = config["reward_gold"]
        self.party = tuple(party)
        require(0 < len(self.party) <= 8, "R41 requires an active party")
        heroes = _source_units(content, "player")
        enemies = _source_units(content, "enemy")
        require(all(uid in heroes for uid in party),
                "R41 party actor is missing from canonical Content")
        require(not set(party).intersection(config["enemies"]),
                "R41 actor identity collision")
        self.skills = deepcopy(content.skills)
        self.actors = {}
        for uid in (*party, *config["enemies"]):
            template = (heroes if uid in party else enemies)[uid]
            require(1 <= template.speed <= 999, "R41 actor speed is unsupported")
            self.actors[uid] = {
                "id": uid, "name": template.name,
                "team": "party" if uid in party else "enemy",
                "hp": template.hp, "max_hp": template.max_hp,
                "mp": template.mp, "max_mp": template.max_mp,
                "attack": template.attack, "defense": template.defense,
                "magic": template.magic, "weapon_power": template.weapon_power,
                "speed": template.speed, "skills": list(template.skills),
                "guard": False,
            }
            if uid in party and hero_progress is not None:
                progress = hero_progress.get(uid)
                require(progress is not None,
                        "Active RPG hero must exist in canonical Campaign")
                row = self.actors[uid]
                row["max_hp"] += (progress.level - 1) * 3
                row["attack"] += (progress.level - 1) // 3
                # Reuse R8 jobs/equipment bonuses, not a competing stat model.
                bonuses = [content.jobs.get(progress.job, {}).get("bonuses", {})]
                for item_id in progress.equipment.values():
                    require(item_id in content.equipment,
                            "Equipped R41 item missing from Content")
                    bonuses.append(content.equipment[item_id].get("bonuses", {}))
                for source in bonuses:
                    for stat, amount in source.items():
                        if stat in ("max_hp", "max_mp", "attack", "defense",
                                    "magic", "weapon_power", "speed"):
                            require(type(amount) is int, "R41 equipment stat is invalid")
                            row[stat] += amount
                row["hp"], row["mp"] = row["max_hp"], row["max_mp"]
                require(1 <= row["speed"] <= 999,
                        "R41 equipped hero speed is out of bounds")
        require(all(0 < a["hp"] <= a["max_hp"] and
                    0 <= a["mp"] <= a["max_mp"] for a in self.actors.values()),
                "Invalid canonical actor vitality for classic encounter")
        require(type(inventory) is dict
                and all(type(k) is str and type(v) is int and v >= 0
                        for k, v in inventory.items()), "Invalid canonical inventory")
        self.start_inventory = deepcopy(inventory)
        self.inventory = deepcopy(inventory)
        self.order = list(rpg_turn_order([
            {"id": a["id"], "speed": a["speed"], "team": a["team"]}
            for a in self.actors.values()]))
        self.cursor = 0
        self.round = 1
        self.result = None
        self.commands = []
        self._auto_enemies()

    def _current(self):
        return self.actors[self.order[self.cursor]]

    def _outcome(self):
        if all(a["hp"] == 0 for a in self.actors.values()
               if a["team"] == "enemy"):
            self.result = "victory"
        elif all(a["hp"] == 0 for a in self.actors.values()
                 if a["team"] == "party"):
            self.result = "defeat"

    def _advance(self):
        self._outcome()
        if self.result:
            return
        for _ in range(len(self.order)):
            self.cursor = (self.cursor + 1) % len(self.order)
            if self.cursor == 0:
                self.round += 1
            actor = self._current()
            if actor["hp"] > 0:
                # Guard absorbs hits until this actor acts again.
                actor["guard"] = False
                return
        require(False, "R41 turn order has no living actors")

    def _hit(self, actor, target, power=0, *, magical=False):
        stat = actor["magic"] if magical else actor["attack"] + actor["weapon_power"]
        reduction = target["defense"] // 2 if magical else target["defense"]
        amount = max(1, stat + power - reduction)
        if target["guard"]:
            amount = max(1, (amount + 1) // 2)
        target["hp"] = max(0, target["hp"] - amount)

    def _act(self, command, *, enemy=False):
        require(type(command) is dict and type(command.get("kind")) is str,
                "Malformed RPG_TURN action")
        actor = self._current()
        require(actor["hp"] > 0, "KO actors cannot take turns")
        require((actor["team"] == "enemy") == enemy,
                "Wrong RPG_TURN actor ownership")
        kind = command["kind"]
        require(command.get("actor") == actor["id"], "Out-of-turn RPG_TURN actor")
        if kind == "guard":
            require(set(command) == {"kind", "actor"}, "Invalid guard fields")
            actor["guard"] = True
        elif kind == "flee":
            require(not enemy and set(command) == {"kind", "actor"},
                    "Invalid flee action")
            self.result = "fled"
        else:
            require(type(command.get("target")) is str
                    and command["target"] in self.actors,
                    "Unknown RPG_TURN target")
            target = self.actors[command["target"]]
            if kind == "attack":
                require(set(command) == {"kind", "actor", "target"}
                        and actor["team"] != target["team"] and target["hp"] > 0,
                        "Attack requires a live enemy")
                self._hit(actor, target)
            elif kind == "skill":
                require(set(command) == {"kind", "actor", "target", "skill"}
                        and type(command.get("skill")) is str
                        and command["skill"] in actor["skills"]
                        and command["skill"] in self.skills,
                        "Unavailable RPG_TURN skill")
                skill = self.skills[command["skill"]]
                require(0 <= skill.cost <= actor["mp"], "Insufficient MP")
                require(skill.effects and all(
                    e.kind in ("damage", "heal") for e in skill.effects),
                    "Unsupported R41 skill effect (requires R43)")
                ally = skill.target in ("ally", "self")
                require(skill.target in ("ally", "self", "enemy")
                        and (actor["team"] == target["team"]) == ally
                        and (skill.target != "self" or target is actor)
                        and target["hp"] > 0,
                        "Invalid RPG_TURN skill target")
                actor["mp"] -= skill.cost
                for effect in skill.effects:
                    if effect.kind == "damage":
                        require(not ally, "Healing targets cannot receive damage spells")
                        self._hit(actor, target, effect.power, magical=skill.magical)
                    else:
                        require(ally, "Enemy-target spells cannot heal allies")
                        target["hp"] = min(target["max_hp"],
                                           target["hp"] + max(0, effect.power))
            elif kind == "item":
                require(not enemy
                        and set(command) == {"kind", "actor", "target", "item"}
                        and command["item"] == "potion"
                        and target["team"] == "party" and target["hp"] > 0
                        and target["hp"] < target["max_hp"],
                        "R41 item use requires a living, injured ally and potion")
                require(self.inventory.get("potion", 0) >= 1,
                        "No canonical potion available")
                self.inventory["potion"] -= 1
                target["hp"] = min(target["max_hp"], target["hp"] + 20)
            else:
                require(False, "Unknown RPG_TURN action")
        if not self.result:
            self._advance()

    def _auto_enemies(self):
        loops = 0
        while not self.result and self._current()["team"] == "enemy":
            loops += 1
            require(loops <= 32, "R41 enemy auto-turn budget exceeded")
            living = [a for a in self.actors.values()
                      if a["team"] == "party" and a["hp"] > 0]
            require(bool(living), "No living party member")
            target = min(living, key=lambda a: (a["hp"], a["id"]))
            self._act({"kind": "attack", "actor": self._current()["id"],
                       "target": target["id"]}, enemy=True)

    def command(self, action):
        require(not self.result and len(self.commands) < MAX_COMMANDS,
                "Encounter resolved or RPG_TURN journal full")
        # GameSession deep-copies the encounter before entering this boundary.
        self._act(action)
        self._auto_enemies()
        self.commands.append(deepcopy(action))
        return self.view()

    def view(self):
        return {"id": self.id, "scene": self.scene, "round": self.round,
                "active": None if self.result else self._current()["id"],
                "order": list(self.order), "result": self.result,
                "actors": deepcopy(list(self.actors.values())),
                "inventory": deepcopy(self.inventory)}

    def recording(self):
        return {"version": VERSION, "id": self.id,
                "party": list(self.party),
                "start_inventory": deepcopy(self.start_inventory),
                "commands": deepcopy(self.commands),
                "view": self.view()}

    @classmethod
    def replay(cls, recording, *, encounter_id, config, party, content,
               hero_progress=None):
        require(type(recording) is dict
                and set(recording) == {"version", "id", "party",
                                       "start_inventory", "commands", "view"}
                and type(recording["version"]) is int
                and recording["version"] == VERSION
                and recording["id"] == encounter_id
                and recording["party"] == list(party)
                and type(recording["commands"]) is list
                and len(recording["commands"]) <= MAX_COMMANDS,
                "Malformed RPG_TURN encounter checkpoint")
        result = cls(encounter_id, config, party, content,
                     recording["start_inventory"], hero_progress=hero_progress)
        for action in recording["commands"]:
            result.command(action)
        require(result.recording() == recording,
                "RPG_TURN checkpoint diverges from command replay")
        return result


__all__ = ["VERSION", "MAX_COMMANDS", "validate_encounters", "ClassicEncounter"]
