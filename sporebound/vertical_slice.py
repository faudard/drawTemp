"""2.8 castle vertical slice: one replayable preparation-to-epilogue journey.

This is a thin, headless product flow over Campaign and MultiFrontSession.
All tactical and strategic outcomes remain owned by those engines.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

from .campaign import Campaign
from .fronts import MultiFrontSession
from .game_session import digest
from .model import Content, require
from .rules import default_rules
from .storage import write_json


APPROACHES = {
    "ram": ("gate", None),
    "infiltration": ("walls", None),
    "tunnels": ("tunnels", "tunnels"),
    "negotiation": ("supplies", None),
    "direct": ("supplies", "direct"),
}


class CastleVerticalSlice:
    """Authenticated choices -> real front battles -> one of three endings.

    `blueprint` consists of the MultiFrontSession constructor's authored
    missions, specs, links, logistics and campaign policy. It is intentionally
    passed in instead of copied into a second scenario rules engine.
    """

    VERSION = 1

    def __init__(self, content: Content, blueprint: dict, *, seed=1,
                 rules=None, squad_ids=("captain", "engineer"), starting_gold=60):
        self.rules = rules if rules is not None else default_rules()
        content.validate(rules=self.rules)
        require(type(seed) is int, "Seed must be an integer")
        require(type(starting_gold) is int and 0 <= starting_gold <= 100000,
                "Invalid preparation budget")
        require(isinstance(blueprint, dict) and
                set(blueprint) == {"missions", "specs", "links", "logistics", "campaign"},
                "Invalid castle blueprint")
        require(set(blueprint["missions"]) == set(blueprint["specs"]) and
                {"gate", "walls", "supplies", "courtyard", "tunnels", "throne"}
                <= set(blueprint["missions"]), "Castle requires all six fronts")
        require(isinstance(squad_ids, (list, tuple)) and squad_ids and
                all(isinstance(uid, str) and bool(uid) for uid in squad_ids) and
                len(set(squad_ids)) == len(squad_ids), "Invalid squad roster")
        for uid in squad_ids:
            require(any(u.id == uid and u.team == "player"
                        for mid in blueprint["missions"].values()
                        for u in content.missions[mid].units), "Unknown squad hero")
        self.content = deepcopy(content)
        self.blueprint = deepcopy(blueprint)
        self.seed = seed
        self.squad_ids = tuple(squad_ids)
        self.squad = list(squad_ids)
        self.starting_gold = starting_gold
        self.roster = Campaign(unlocked=list(self.content.missions),
                               gold=starting_gold)
        self.preparation = []
        self.approach = None
        self.fronts = None
        self.conceded = False

    def _preparing(self):
        require(self.fronts is None, "Preparation is locked after departure")

    def _playing(self):
        require(self.fronts is not None and self.ending is None,
                "The castle campaign is not accepting commands")
        return self.fronts

    def select_squad(self, members):
        self._preparing()
        require(isinstance(members, (list, tuple)) and
                1 <= len(members) <= len(self.squad_ids) and
                len(set(members)) == len(members) and
                set(members) <= set(self.squad_ids),
                "Select one or more distinct available heroes")
        self.squad = list(members)
        self.preparation.append({"kind": "squad", "members": list(members)})

    def set_job(self, hero, job):
        self._preparing()
        require(hero in self.squad_ids, "Unknown playable hero")
        self.roster.set_job(self.content, hero, job)
        self.preparation.append({"kind": "job", "hero": hero, "job": job})

    def buy(self, item):
        self._preparing()
        self.roster.buy(self.content, item)
        self.preparation.append({"kind": "buy", "item": item})

    def equip(self, hero, item):
        self._preparing()
        require(hero in self.squad_ids, "Unknown playable hero")
        self.roster.equip(self.content, hero, item)
        self.preparation.append({"kind": "equip", "hero": hero, "item": item})

    def _prepared_content(self):
        prepared = deepcopy(self.content)
        for mission in prepared.missions.values():
            mission.units = [
                u for u in mission.units
                if u.team != "player" or u.id not in self.squad_ids or u.id in self.squad
            ]
        prepared.validate(rules=self.rules)
        # Campaign.prepare applies class, talent and equipment bonuses using
        # the same rules as the standard campaign; it does not simulate a win.
        for mid in self.blueprint["missions"].values():
            battle = self.roster.prepare(prepared, mid, seed=self.seed,
                                         ruleset=self.rules)
            prepared.missions[mid] = deepcopy(battle.content.missions[mid])
        prepared.validate(rules=self.rules)
        return prepared

    def start(self, approach):
        self._preparing()
        require(approach in APPROACHES, "Unknown castle approach")
        focused, route = APPROACHES[approach]
        candidate = MultiFrontSession(
            self._prepared_content(), self.blueprint["missions"], focused,
            seed=self.seed, rules=self.rules,
            specs=self.blueprint["specs"], links=self.blueprint["links"],
            logistics=self.blueprint["logistics"],
            campaign=self.blueprint["campaign"])
        if route is not None:
            candidate.select_route(route)
        self.fronts = candidate
        self.approach = approach
        return self.fronts.active

    @property
    def ending(self):
        if self.conceded:
            return "defeat"
        if self.fronts is None:
            return None
        status = self.fronts.state()["campaign"]["status"]
        if status == "defeat":
            return "defeat"
        if status == "victory":
            return ("accord" if self.fronts.timeline.fronts["gate"]["status"]
                    == "negotiated" else "victory")
        return None

    @property
    def chapter(self):
        if self.fronts is None:
            return "preparation"
        if self.ending is not None:
            return "epilogue"
        if self.fronts.timeline.focused == "throne":
            return "throne"
        return "siege" if len(self.fronts.battles) > 1 else "approach"

    def execute(self, command):
        return self._playing().execute(command)

    def switch(self, front):
        return self._playing().switch(front)

    def advance(self):
        return self._playing().advance()

    def doctrine(self, front, value):
        return self._playing().set_doctrine(front, value)

    def negotiate(self, front="gate"):
        return self._playing().negotiate_front(front)

    def partial(self, front="courtyard"):
        return self._playing().partial_front(front)

    def withdraw(self, front):
        return self._playing().withdraw_front(front)

    def select_route(self, route):
        return self._playing().select_route(route)

    def concede(self):
        self._playing()
        self.conceded = True

    def state(self):
        if self.fronts is None:
            return {"chapter": "preparation", "approaches": sorted(APPROACHES),
                    "squad": list(self.squad), "gold": self.roster.gold,
                    "inventory": deepcopy(self.roster.inventory),
                    "heroes": {uid: {"job": self.roster.hero(uid).job,
                                     "equipment": deepcopy(self.roster.hero(uid).equipment)}
                               for uid in self.squad_ids}}
        front_state = self.fronts.state()
        throne = self.fronts.battles.get("throne")
        return {"chapter": self.chapter, "approach": self.approach,
                "ending": self.ending, "focused": self.fronts.timeline.focused,
                "strategic_turn": self.fronts.timeline.turn,
                "fronts": deepcopy(self.fronts.timeline.fronts),
                "campaign": front_state["campaign"],
                "supplies": deepcopy(self.fronts.logistics.supplies),
                "boss_phase_triggered": bool(throne and
                                              "castellan_second_phase" in throne.fired),
                "links": sorted(self.fronts.applied_links),
                "tactical_result": self.fronts.active.result,
                "deploying": self.fronts.active.deploying}

    def recording(self):
        payload = {"version": self.VERSION, "kind": "castle_vertical_slice",
                   "seed": self.seed, "starting_gold": self.starting_gold,
                   "squad_ids": list(self.squad_ids),
                   "authored_digest": digest(self.content.to_dict()),
                   "blueprint_digest": digest(self.blueprint),
                   "rules": self.rules.manifest(),
                   "preparation": deepcopy(self.preparation),
                   "approach": self.approach, "conceded": self.conceded,
                   "fronts": self.fronts.recording() if self.fronts else None}
        return {**payload, "digest": digest(payload)}

    def save(self, path):
        write_json(path, self.recording())
        return Path(path)

    @classmethod
    def from_recording(cls, data, content, blueprint, *, rules=None):
        rules = rules if rules is not None else default_rules()
        require(isinstance(data, dict) and set(data) == {
            "version", "kind", "seed", "starting_gold", "squad_ids",
            "authored_digest", "blueprint_digest", "rules", "preparation",
            "approach", "conceded", "fronts", "digest"},
            "Invalid castle checkpoint structure")
        require(data["version"] == cls.VERSION and
                data["kind"] == "castle_vertical_slice" and
                data["rules"] == rules.manifest() and
                data["authored_digest"] == digest(content.to_dict()) and
                data["blueprint_digest"] == digest(blueprint),
                "Incompatible castle content, blueprint or rules")
        require(digest({k: v for k, v in data.items() if k != "digest"})
                == data["digest"], "Castle checkpoint checksum mismatch")
        require(isinstance(data["preparation"], list) and
                type(data["conceded"]) is bool, "Invalid castle checkpoint")
        result = cls(content, blueprint, seed=data["seed"], rules=rules,
                     squad_ids=data["squad_ids"],
                     starting_gold=data["starting_gold"])
        for action in data["preparation"]:
            require(isinstance(action, dict) and "kind" in action,
                    "Invalid preparation action")
            if action["kind"] == "squad":
                require(set(action) == {"kind", "members"}, "Invalid squad action")
                result.select_squad(action["members"])
            elif action["kind"] == "job":
                require(set(action) == {"kind", "hero", "job"}, "Invalid job action")
                result.set_job(action["hero"], action["job"])
            elif action["kind"] == "buy":
                require(set(action) == {"kind", "item"}, "Invalid buy action")
                result.buy(action["item"])
            elif action["kind"] == "equip":
                require(set(action) == {"kind", "hero", "item"}, "Invalid equip action")
                result.equip(action["hero"], action["item"])
            else:
                require(False, "Unknown preparation action")
        if data["approach"] is None:
            require(data["fronts"] is None and not data["conceded"],
                    "Unstarted campaign cannot have a battle or ending")
        else:
            result.start(data["approach"])
            expected = result.fronts.recording()
            stored = data["fronts"]
            require(isinstance(stored, dict) and
                    all(expected[key] == stored.get(key)
                        for key in expected if key not in {"operations", "digest"}),
                    "Castle front configuration differs from prepared roster")
            restored = MultiFrontSession.replay(stored, rules=rules)
            result.fronts = restored
            if data["conceded"]:
                result.concede()
        require(result.recording() == data, "Castle checkpoint does not reproduce")
        return result

    @classmethod
    def load(cls, path, content, blueprint, *, rules=None):
        return cls.from_recording(json.loads(Path(path).read_text(encoding="utf-8")),
                                  content, blueprint, rules=rules)
