"""Deterministic multi-encounter scenario progression, independent of rendering.

A phase has a mission id and exits with explicit destinations. Branch decisions
are made between encounters, never during an active Battle.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from .model import require


@dataclass
class ScenarioDirector:
    phases: dict
    current: str
    history: list = field(default_factory=list)
    flags: dict = field(default_factory=dict)
    completed: bool = False

    @classmethod
    def from_dict(cls, data):
        require(isinstance(data, dict) and isinstance(data.get("phases"), list),
                "Scenario needs phases")
        phases = {}
        for phase in data["phases"]:
            require(isinstance(phase, dict) and isinstance(phase.get("id"), str)
                    and bool(phase["id"]) and phase["id"] not in phases,
                    "Duplicate or invalid phase")
            require(isinstance(phase.get("mission"), str) and bool(phase["mission"]),
                    "Phase needs mission")
            require(isinstance(phase.get("exits", {}), dict), "Phase exits must be an object")
            phases[phase["id"]] = deepcopy(phase)
        start = data.get("start")
        require(start in phases, "Unknown starting phase")
        for phase in phases.values():
            for destination in phase.get("exits", {}).values():
                require(destination is None or destination in phases, "Unknown destination phase")
        return cls(phases, start)

    def available_choices(self):
        if self.completed:
            return []
        return sorted(self.phases[self.current].get("exits", {}))

    def mission_id(self):
        require(not self.completed, "Scenario completed")
        return self.phases[self.current]["mission"]

    def advance(self, result, choice):
        """Commit a completed encounter and select exactly one valid branch."""
        require(not self.completed, "Scenario completed")
        require(result in {"victory", "defeat"}, "Encounter must have a terminal result")
        exits = self.phases[self.current].get("exits", {})
        require(choice in exits, "Invalid scenario choice")
        source = self.current
        destination = exits[choice]
        self.history.append({"phase": source, "mission": self.mission_id(),
                             "result": result, "choice": choice})
        self.flags.update(deepcopy(self.phases[source].get("on_exit", {}).get(choice, {})))
        if destination is None:
            self.completed = True
        else:
            self.current = destination
        return destination

    def state(self):
        return {"current": self.current, "history": deepcopy(self.history),
                "flags": deepcopy(self.flags), "completed": self.completed}

    def restore(self, state):
        require(isinstance(state, dict) and state.get("current") in self.phases,
                "Invalid scenario state")
        require(isinstance(state.get("history"), list)
                and isinstance(state.get("flags"), dict)
                and type(state.get("completed")) is bool, "Invalid scenario state")
        self.current = state["current"]
        self.history = deepcopy(state["history"])
        self.flags = deepcopy(state["flags"])
        self.completed = state["completed"]


class ScenarioSession:
    """Owns one active Battle and transfers persistent campaign state between phases."""

    def __init__(self, content, scenario, *, seed=1, rules=None):
        from .engine import Battle
        self.content = content
        self.director = scenario
        self.seed = seed
        self.rules = rules
        self.roster = {}
        self.inventory = None
        self.battle = Battle(content, scenario.mission_id(), seed=seed, rules=rules)
        self._apply_campaign_state()

    def _apply_campaign_state(self):
        if self.inventory is not None:
            self.battle.inventory["player"] = deepcopy(self.inventory)
        for unit in self.battle.units:
            previous = self.roster.get(unit.id)
            if previous and unit.team == "player":
                unit.hp = max(0, min(unit.max_hp, previous["hp"]))
                unit.mp = max(0, min(unit.max_mp, previous["mp"]))
                unit.statuses = deepcopy(previous["statuses"])

    def complete(self, choice):
        """Advance only after a terminal battle outcome; preserve surviving allies."""
        require(self.battle.result in {"victory", "defeat"},
                "Cannot leave an unfinished battle")
        outcome = self.battle.result
        for unit in self.battle.units:
            if unit.team == "player":
                self.roster[unit.id] = {
                    "hp": unit.hp, "mp": unit.mp, "statuses": deepcopy(unit.statuses)}
        self.inventory = deepcopy(self.battle.inventory["player"])
        next_phase = self.director.advance(outcome, choice)
        if next_phase is None:
            self.battle = None
            return None
        from .engine import Battle
        self.battle = Battle(self.content, self.director.mission_id(),
                             seed=self.seed + len(self.director.history), rules=self.rules)
        self._apply_campaign_state()
        return self.battle

    def state(self):
        return {"scenario": self.director.state(), "roster": deepcopy(self.roster),
                "inventory": deepcopy(self.inventory)}
