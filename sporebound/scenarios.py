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
            require(phase.get("required_result") in {None, "victory", "defeat"}, "Invalid required result")
            effects = phase.get('entry_effects', [])
            require(isinstance(effects, list), 'Entry effects must be a list')
            for effect in effects:
                require(isinstance(effect, dict) and isinstance(effect.get('flag'), str)
                        and 'equals' in effect, 'Invalid entry condition')
                require(isinstance(effect.get('objects', {}), dict)
                        and isinstance(effect.get('statuses', {}), dict), 'Invalid entry effects')
                for statuses in effect.get('statuses', {}).values():
                    require(isinstance(statuses, dict) and all(isinstance(k, str) and type(v) is int and v > 0
                                                               for k, v in statuses.items()), 'Invalid status consequence')
                for changes in effect.get('objects', {}).values():
                    require(isinstance(changes, dict) and set(changes) <= {'disabled', 'charges', 'enabled'},
                            'Unsupported object consequence')
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
        expected = self.phases[self.current].get("required_result")
        require(expected is None or result == expected, "This phase requires " + str(expected))
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
    """Owns deterministic transitions and a verified journal of every encounter."""

    def __init__(self, content, scenario, *, seed=1, rules=None):
        from .rules import default_rules
        require(not scenario.history and not scenario.completed, 'Start with a fresh scenario director')
        self.content = deepcopy(content)
        self.director = deepcopy(scenario)
        self.definition = {'start': scenario.current, 'phases': deepcopy(list(scenario.phases.values()))}
        self.seed = seed
        self.rules = rules if rules is not None else default_rules()
        self.roster = {}
        self.inventory = None
        self.elapsed_ticks = 0
        self.journal = []
        self.battle = self._new_battle()

    def _new_battle(self):
        from .engine import Battle
        content = deepcopy(self.content)
        phase = self.director.phases[self.director.current]
        require(phase['mission'] in content.missions, 'Unknown scenario mission')
        mission = content.missions[phase['mission']]
        for consequence in phase.get('entry_effects', []):
            if (consequence['flag'] not in self.director.flags
                    or self.director.flags[consequence['flag']] != consequence['equals']):
                continue
            for oid, changes in consequence.get('objects', {}).items():
                obj = next((o for o in mission.objects if o['id'] == oid), None)
                require(obj is not None, 'Unknown consequence object')
                obj.update(deepcopy(changes))
            for uid, statuses in consequence.get('statuses', {}).items():
                unit = next((u for u in mission.units if u.id == uid), None)
                require(unit is not None, 'Unknown consequence unit')
                unit.statuses.update(deepcopy(statuses))
        players = {u.id: u for u in mission.units if u.team == 'player'}
        setup = {'units': {uid: {**deepcopy(row),
                                'hp': min(players[uid].max_hp, row['hp']),
                                'mp': min(players[uid].max_mp, row['mp'])}
                           for uid, row in self.roster.items() if uid in players}}
        if self.inventory is not None:
            setup['inventory'] = deepcopy(self.inventory)
        return Battle(content, mission.id, seed=self.seed + len(self.director.history),
                      rules=self.rules, initial_state=setup)

    def complete(self, choice):
        """Commit transition atomically, including entry effects and initialization."""
        snapshot = deepcopy(self.__dict__)
        try:
            return self._complete(choice)
        except Exception:
            self.__dict__ = snapshot
            raise

    def _complete(self, choice):
        require(self.battle is not None and self.battle.result in {'victory', 'defeat'},
                'Cannot leave an unfinished battle')
        outcome = self.battle.result
        stage = {'commands': deepcopy(self.battle.commands), 'digest': self.battle.digest(),
                 'choice': choice}
        for unit in self.battle.units:
            if unit.team == 'player':
                self.roster[unit.id] = {'hp': unit.hp, 'mp': unit.mp,
                                        'statuses': deepcopy(unit.statuses)}
        self.inventory = deepcopy(self.battle.inventory['player'])
        self.elapsed_ticks += self.battle.tick
        next_phase = self.director.advance(outcome, choice)
        self.journal.append(stage)
        self.battle = self._new_battle() if next_phase is not None else None
        return self.battle

    def state(self):
        return {'scenario': self.director.state(), 'roster': deepcopy(self.roster),
                'inventory': deepcopy(self.inventory), 'elapsed_ticks': self.elapsed_ticks}

    def digest(self):
        import hashlib
        import json
        state = {**self.state(), 'battle': self.battle.digest() if self.battle else None}
        return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()

    def recording(self):
        return {'version': 1, 'kind': 'scenario', 'content': self.content.to_dict(),
                'scenario': deepcopy(self.definition), 'seed': self.seed,
                'rules': self.rules.manifest(), 'journal': deepcopy(self.journal),
                'current': {'commands': deepcopy(self.battle.commands), 'digest': self.battle.digest()}
                           if self.battle else None,
                'digest': self.digest()}

    @classmethod
    def replay(cls, recording, *, rules=None):
        from .model import Content
        from .rules import default_rules
        rules = rules if rules is not None else default_rules()
        require(recording.get('version') == 1 and recording.get('kind') == 'scenario',
                'Unsupported scenario save')
        require(recording.get('rules') == rules.manifest(), 'Scenario ruleset mismatch')
        session = cls(Content.from_dict(recording['content'], rules=rules),
                      ScenarioDirector.from_dict(recording['scenario']), seed=recording['seed'], rules=rules)
        for stage in recording['journal']:
            require(session.battle is not None, 'Unexpected encounter after scenario completion')
            for command in stage['commands']:
                session.battle.execute(command)
            require(session.battle.digest() == stage['digest'], 'Encounter checksum mismatch')
            session.complete(stage['choice'])
        current = recording['current']
        require((current is None) == (session.battle is None), 'Invalid current encounter')
        if current is not None:
            for command in current['commands']:
                session.battle.execute(command)
            require(session.battle.digest() == current['digest'], 'Current encounter checksum mismatch')
        require(session.digest() == recording['digest'], 'Scenario checksum mismatch')
        return session
