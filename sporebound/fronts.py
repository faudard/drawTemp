"""Global strategic clock for several simultaneous tactical fronts.

Inactive fronts resolve one deterministic strategic step at each synchronization.
The focused front is never auto-resolved. All fronts share one clock.
"""
from copy import deepcopy
from .model import require
from . import front_links
from .logistics import LogisticsDirector, destination_actors

DOCTRINES = {"hold", "assault", "delay", "retreat"}


class FrontDirector:
    def __init__(self, fronts, focused, *, seed=1):
        require(isinstance(fronts, dict) and bool(fronts), "Fronts must be a nonempty mapping")
        require(focused in fronts, "Unknown focused front")
        self.fronts = {}
        for name, spec in fronts.items():
            require(isinstance(name, str) and name and isinstance(spec, dict), "Invalid front")
            doctrine = spec.get("doctrine", "hold")
            require(doctrine in DOCTRINES, "Unknown front doctrine")
            strength = spec.get("strength", 10)
            opposition = spec.get("opposition", 10)
            require(all(type(n) is int and 0 <= n <= 10000 for n in (strength, opposition)),
                    "Invalid front strength")
            self.fronts[name] = {"strength": strength, "opposition": opposition,
                                 "doctrine": doctrine, "status": "active"}
        require(type(seed) is int, "Seed must be an integer")
        self.seed = seed
        self.focused = focused
        self.turn = 0
        self.events = []

    def switch(self, front):
        require(front in self.fronts, "Unknown front")
        require(self.fronts[front]["status"] == "active", "Front already resolved")
        previous = self.focused
        self.focused = front
        self.events.append({"turn": self.turn, "kind": "focus_changed",
                            "from": previous, "to": front})

    def set_doctrine(self, front, doctrine):
        require(front in self.fronts and doctrine in DOCTRINES, "Invalid doctrine")
        require(self.fronts[front]["status"] == "active", "Front already resolved")
        self.fronts[front]["doctrine"] = doctrine

    def advance(self):
        """One strategic turn; automatic results do not depend on iteration order."""
        self.turn += 1
        for name in sorted(self.fronts):
            if name == self.focused:
                continue
            front = self.fronts[name]
            if front["status"] != "active":
                continue
            doctrine = front["doctrine"]
            attack = {"hold": 1, "assault": 3, "delay": 0, "retreat": 0}[doctrine]
            defense = {"hold": 2, "assault": 0, "delay": 1, "retreat": 3}[doctrine]
            front["opposition"] = max(0, front["opposition"] - min(front["strength"], attack))
            front["strength"] = max(0, front["strength"] - max(0, 2 - defense))
            if doctrine == "retreat":
                front["status"] = "withdrawn"
            elif front["opposition"] == 0:
                front["status"] = "victory"
            elif front["strength"] == 0:
                front["status"] = "defeat"
            self.events.append({"turn": self.turn, "kind": "front_resolved",
                                "front": name, **deepcopy(front)})
        return self.state()

    def state(self):
        return {"turn": self.turn, "focused": self.focused,
                "fronts": deepcopy(self.fronts), "events": deepcopy(self.events)}

    def restore(self, state):
        require(isinstance(state, dict) and type(state.get("turn")) is int
                and state["turn"] >= 0 and state.get("focused") in self.fronts,
                "Invalid front state")
        require(isinstance(state.get("fronts"), dict)
                and set(state["fronts"]) == set(self.fronts)
                and isinstance(state.get("events"), list), "Invalid front state")
        self.turn = state["turn"]
        self.focused = state["focused"]
        self.fronts = deepcopy(state["fronts"])
        self.events = deepcopy(state["events"])


class MultiFrontSession:
    """Deterministic tactical/strategic session with an explicit command journal.

    Use execute() rather than calling active.execute() directly when a session
    must be saved or replayed. Strategic changes are not Battle commands: only
    the multi-front journal can reconstruct offscreen attrition.
    """

    def __init__(self, content, missions, focused, *, seed=1, rules=None, specs=None, links=None, logistics=None):
        from .engine import Battle
        from .rules import default_rules
        require(isinstance(missions, dict) and bool(missions) and focused in missions,
                "Invalid multi-front missions")
        require(all(isinstance(name, str) and name and isinstance(mid, str)
                    and mid in content.missions for name, mid in missions.items()),
                "Unknown front mission")
        definitions = deepcopy(specs) if specs is not None else {name: {} for name in missions}
        require(isinstance(definitions, dict) and set(definitions) == set(missions),
                "Front specifications must match mission names")
        self.content = deepcopy(content)
        self.missions = dict(missions)
        self.rules = rules if rules is not None else default_rules()
        self.seed = seed
        self.initial_focus = focused
        self.initial_specs = deepcopy(definitions)
        self.timeline = FrontDirector(definitions, focused, seed=seed)
        self.initial_fronts = deepcopy(self.timeline.fronts)
        self.battles = {}
        self.front_snapshots = {}
        self.pending_reinforcements = {}
        self.history = []
        self.initial_logistics = deepcopy(logistics) if logistics is not None else None
        self.logistics = (LogisticsDirector(self.initial_logistics, self.missions)
                          if self.initial_logistics is not None else None)
        self.links = deepcopy(links if links is not None else [])
        front_links.validate(self.content, self.missions, self.links)
        self.applied_links = set()
        self.front_overrides = {}
        self.blocked_reinforcements = set()
        self.battles[focused] = self._new_battle(focused)

    def _new_battle(self, front):
        from .engine import Battle
        prepared = deepcopy(self.content)
        front_links.configure_mission(
            prepared, self.missions[front], self.front_overrides.get(front, {}),
            front in self.blocked_reinforcements)
        return Battle(prepared, self.missions[front],
                      seed=self.seed + sorted(self.missions).index(front)
                      if front != self.initial_focus else self.seed,
                      rules=self.rules)

    @property
    def active(self):
        return self.battles[self.timeline.focused]

    def execute(self, command):
        """Execute exactly one player/AI command on the focused front."""
        require(isinstance(command, dict), "Expected tactical command")
        # Battle.execute is transactional. Linking other fronts must be just as
        # atomic, including their events, aggregate scores and future overrides.
        snapshot = deepcopy((self.timeline, self.battles, self.front_overrides,
                             self.blocked_reinforcements, self.pending_reinforcements,
                             self.applied_links))
        source = self.timeline.focused
        try:
            start = len(self.active.events)
            self.active.execute(deepcopy(command))
            for event in self.battles[source].events[start:]:
                for link in self.links:
                    if (link["source"] == source and link["id"] not in self.applied_links
                            and front_links.match(link, event)):
                        front_links.apply(self, link)
        except Exception:
            (self.timeline, self.battles, self.front_overrides,
             self.blocked_reinforcements, self.pending_reinforcements,
             self.applied_links) = snapshot
            raise
        self.history.append({"kind": "execute", "command": deepcopy(command)})

    def set_doctrine(self, front, doctrine):
        self.timeline.set_doctrine(front, doctrine)
        self.history.append({"kind": "doctrine", "front": front, "doctrine": doctrine})

    def switch(self, front):
        require(front in self.missions, "Unknown front")
        require(self.active.active is None or (not self.active.active.moved
                and not self.active.active.acted),
                "Finish the active unit turn before switching fronts")
        snapshot = deepcopy((self.timeline, self.battles, self.front_snapshots,
                             self.pending_reinforcements))
        try:
            self.timeline.switch(front)
            if front not in self.battles:
                self.battles[front] = self._new_battle(front)
                # An unopened front has already fought its offscreen turns.
                # Materialize those losses once when it first gains focus.
                initial = self.initial_fronts[front]
                current = self.timeline.fronts[front]
                self._apply_attrition(self.battles[front], "player",
                                      initial["strength"] - current["strength"])
                self._apply_attrition(self.battles[front], "enemy",
                                      initial["opposition"] - current["opposition"])
            self.front_snapshots.pop(front, None)
            self._deliver_reinforcements(front)
        except Exception:
            (self.timeline, self.battles, self.front_snapshots,
             self.pending_reinforcements) = snapshot
            raise
        self.history.append({"kind": "switch", "front": front})
        return self.active

    def reinforce(self, front, actors, *, lifetime=None):
        """Queue a concrete wave for either a loaded or an unopened front."""
        from .encounters import EncounterDirector
        require(front in self.missions and self.timeline.fronts[front]["status"] == "active",
                "Unknown or inactive reinforcement front")
        require(front not in self.blocked_reinforcements,
                "Reinforcements interdicted on this front")
        # Validate capacity and lifetime now, not after the player switches.
        EncounterDirector().queue(actors, lifetime=lifetime)
        self.pending_reinforcements.setdefault(front, []).append(
            {"actors": deepcopy(actors), "lifetime": lifetime})
        self.timeline.events.append({"turn": self.timeline.turn, "kind": "reinforcement_queued",
                                     "front": front, "count": len(actors)})
        self.history.append({"kind": "reinforce", "front": front,
                             "actors": deepcopy(actors), "lifetime": lifetime})

    def _deliver_reinforcements(self, front):
        battle = self.battles[front]
        waves = self.pending_reinforcements.pop(front, [])
        for wave in waves:
            battle.queue_wave(wave["actors"], lifetime=wave["lifetime"])

    def _check_convoy_destination(self, front, actors):
        require(self.timeline.fronts[front]["status"] == "active",
                "Destination front is no longer active")
        require(front not in self.blocked_reinforcements,
                "The destination is under reinforcement interdiction")
        return destination_actors(self, front, actors)

    def send_reserves(self, destination, actors):
        """Spend a finite strategic pool and send one bounded convoy.

        The destination must have an authored reserve route. This never
        creates tactical units until a later strategic synchronization.
        """
        require(self.logistics is not None, "Strategic logistics not configured")
        require(destination in self.missions, "Unknown reserve destination")
        snapshot = deepcopy((self.logistics, self.timeline))
        try:
            validated = self._check_convoy_destination(destination, actors)
            teams = {actor["team"] for actor in validated}
            require(len(teams) == 1, "Reserve convoy must use one team")
            team = next(iter(teams))
            require(self.logistics.reserves[team] >= len(validated),
                    "Insufficient strategic reserves")
            convoy_id = self.logistics.order(
                "reserve", destination, validated, team, self.timeline.turn)
            self.logistics.reserves[team] -= len(validated)
            self.timeline.events.append({
                "turn": self.timeline.turn, "kind": "reserves_dispatched",
                "convoy": convoy_id, "front": destination, "team": team,
                "count": len(validated)})
        except Exception:
            self.logistics, self.timeline = snapshot
            raise
        self.history.append({"kind": "send_reserves", "front": destination,
                             "actors": deepcopy(actors)})
        return convoy_id

    def transfer_units(self, destination, placements):
        """Move idle living players from the focused battle to another front.

        placements: {unit_id: [x, y]}. Members leave their original Battle
        immediately; current CT, casting and reaction reservations do not
        travel. HP, MP, equipment stats and statuses survive the journey.
        """
        from dataclasses import asdict
        require(self.logistics is not None, "Strategic logistics not configured")
        source = self.timeline.focused
        require(destination in self.missions and destination != source,
                "Invalid transfer destination")
        require(isinstance(placements, dict) and bool(placements),
                "Transfer needs unit placements")
        battle = self.active
        require(not battle.deploying and battle.result is None,
                "Finish deployment before transfers")
        selected = []
        for uid, pos in sorted(placements.items()):
            require(isinstance(uid, str) and bool(uid), "Invalid transfer id")
            actor = next((u for u in battle.units if u.id == uid), None)
            require(actor is not None and actor.alive and actor.team == "player",
                    "Only living friendly actors can transfer")
            require(actor.id != battle.active_id and actor.id != battle.carrier
                    and actor.id != battle.mission.protected_id,
                    "Active, carrying or protected actors cannot depart")
            require(actor.kind != "summon" and actor.cast is None
                    and not actor.moved and not actor.acted
                    and actor.id not in battle.summon_owners,
                    "Actor must be an idle permanent unit")
            definition = asdict(actor)
            definition.update(pos=pos, ct=0, moved=False, acted=False,
                              cast=None, disengaging=False)
            selected.append(definition)
        remaining = sum(u.alive and u.team == "player"
                        and u.id not in placements for u in battle.units)
        require(remaining > 0, "A front must retain a friendly defender")
        snapshot = deepcopy((self.timeline, self.battles, self.logistics))
        try:
            validated = self._check_convoy_destination(destination, selected)
            convoy_id = self.logistics.order(source, destination, validated,
                                             "player", self.timeline.turn)
            for definition in selected:
                battle.despawn_actor(definition["id"])
            own_front = self.timeline.fronts[source]
            own_front["strength"] = max(0, own_front["strength"] - len(selected))
            self.timeline.events.append({
                "turn": self.timeline.turn, "kind": "units_departed",
                "convoy": convoy_id, "from": source, "to": destination,
                "units": [actor["id"] for actor in selected]})
        except Exception:
            self.timeline, self.battles, self.logistics = snapshot
            raise
        self.history.append({"kind": "transfer_units", "destination": destination,
                             "placements": deepcopy(placements)})
        return convoy_id

    def _arrive_convoys(self):
        if self.logistics is None:
            return
        for convoy in self.logistics.due(self.timeline.turn):
            front = convoy["to"]
            if (self.timeline.fronts[front]["status"] != "active"
                    or front in self.blocked_reinforcements):
                self.timeline.events.append({
                    "turn": self.timeline.turn, "kind": "convoy_lost",
                    "convoy": convoy["id"], "front": front,
                    "reason": "front_inactive" if self.timeline.fronts[front]["status"]
                    != "active" else "interdicted"})
                continue
            self.pending_reinforcements.setdefault(front, []).append({
                "actors": deepcopy(convoy["actors"]), "lifetime": None})
            row = self.timeline.fronts[front]
            field = "strength" if convoy["team"] == "player" else "opposition"
            row[field] = min(10000, row[field] + len(convoy["actors"]))
            self.timeline.events.append({
                "turn": self.timeline.turn, "kind": "convoy_arrived",
                "convoy": convoy["id"], "front": front,
                "count": len(convoy["actors"]), "team": convoy["team"]})

    def advance(self):
        """One strategic turn; automatic fights never execute tactical AI."""
        snapshot = deepcopy((self.timeline, self.battles, self.front_snapshots,
                             self.pending_reinforcements, self.logistics))
        try:
            for name, battle in self.battles.items():
                if battle.result in {"victory", "defeat"}:
                    self.timeline.fronts[name]["status"] = battle.result
            before = deepcopy(self.timeline.fronts)
            self.timeline.advance()
            self._arrive_convoys()
            self._deliver_reinforcements(self.timeline.focused)
            for name, battle in self.battles.items():
                if name == self.timeline.focused or battle.result is not None:
                    continue
                old, new = before[name], self.timeline.fronts[name]
                if old["status"] != "active":
                    continue
                self._apply_attrition(battle, "player",
                                      old["strength"] - new["strength"])
                self._apply_attrition(battle, "enemy",
                                      old["opposition"] - new["opposition"])
                if new["status"] in {"victory", "defeat"}:
                    loser = "enemy" if new["status"] == "victory" else "player"
                    self._apply_attrition(battle, loser, 1000000)
                    battle.result = new["status"]
                    battle.active_id = None
                    battle.emit("battle_end", result=battle.result)
            for name, front in self.timeline.fronts.items():
                if name != self.timeline.focused and name in self.battles:
                    self.front_snapshots[name] = deepcopy(front)
        except Exception:
            (self.timeline, self.battles, self.front_snapshots,
             self.pending_reinforcements, self.logistics) = snapshot
            raise
        self.history.append({"kind": "advance"})
        return self.timeline.state()

    @staticmethod
    def _apply_attrition(battle, team, amount):
        """Apply strategic losses in stable unit order without running CT ticks."""
        remaining = max(0, amount)
        total = 0
        for unit in sorted((u for u in battle.units if u.team == team and u.alive),
                           key=lambda u: u.id):
            if remaining == 0:
                break
            damage = min(unit.hp, remaining)
            unit.hp -= damage
            total += damage
            remaining -= damage
        if total:
            battle.emit("strategic_attrition", team=team, amount=total)

    def state(self):
        state = {"timeline": self.timeline.state(), "missions": dict(self.missions),
                 "battles": {name: battle.state() for name, battle in sorted(self.battles.items())},
                 "front_snapshots": deepcopy(self.front_snapshots),
                 "pending_reinforcements": deepcopy(self.pending_reinforcements)}
        # Preserve version-1 checksum semantics for sessions without links.
        if self.logistics is not None:
            state["logistics"] = self.logistics.state()
        if self.links:
            state["links"] = deepcopy(self.links)
            state["applied_links"] = sorted(self.applied_links)
            state["front_overrides"] = deepcopy(self.front_overrides)
            state["blocked_reinforcements"] = sorted(self.blocked_reinforcements)
        return state

    def digest(self):
        import hashlib
        import json
        return hashlib.sha256(json.dumps(self.state(), sort_keys=True).encode()).hexdigest()

    def recording(self):
        """Portable journal; replay proves all tactical and strategic mutations."""
        return {"version": 3 if self.logistics is not None else 2, "kind": "multi_front",
                "content": self.content.to_dict(), "missions": dict(self.missions),
                "focused": self.initial_focus, "specs": deepcopy(self.initial_specs),
                "links": deepcopy(self.links),
                **({"logistics": deepcopy(self.initial_logistics)}
                   if self.logistics is not None else {}),
                "seed": self.seed, "rules": self.rules.manifest(),
                "operations": deepcopy(self.history), "digest": self.digest()}

    @classmethod
    def replay(cls, recording, *, rules=None):
        from .model import Content
        from .rules import default_rules
        require(isinstance(recording, dict) and recording.get("version") in {1, 2, 3}
                and recording.get("kind") == "multi_front", "Unsupported multi-front save")
        effective_rules = rules if rules is not None else default_rules()
        require(recording.get("rules") == effective_rules.manifest(),
                "Multi-front ruleset mismatch")
        session = cls(Content.from_dict(recording["content"], rules=effective_rules),
                      recording["missions"], recording["focused"],
                      seed=recording["seed"], rules=effective_rules,
                      specs=recording["specs"],
                      links=recording.get("links", []) if recording["version"] >= 2 else [],
                      logistics=recording["logistics"] if recording["version"] == 3 else None)
        for operation in recording["operations"]:
            kind = operation["kind"]
            if kind == "execute":
                session.execute(operation["command"])
            elif kind == "switch":
                session.switch(operation["front"])
            elif kind == "advance":
                session.advance()
            elif kind == "doctrine":
                session.set_doctrine(operation["front"], operation["doctrine"])
            elif kind == "reinforce":
                session.reinforce(operation["front"], operation["actors"],
                                  lifetime=operation["lifetime"])
            elif kind == "send_reserves":
                session.send_reserves(operation["front"], operation["actors"])
            elif kind == "transfer_units":
                session.transfer_units(operation["destination"], operation["placements"])
            else:
                require(False, "Unknown multi-front operation")
        require(session.digest() == recording["digest"], "Multi-front checksum mismatch")
        return session

    def restore(self, recording):
        """Reconstruct combat from an authenticated journal, never from Battle.state()."""
        require(isinstance(recording, dict) and recording.get("kind") == "multi_front",
                "Pass a multi-front recording, not a public state snapshot")
        restored = self.replay(recording, rules=self.rules)
        require(restored.missions == self.missions
                and restored.content.to_dict() == self.content.to_dict()
                and restored.links == self.links
                and restored.initial_logistics == self.initial_logistics,
                "Incompatible multi-front save")
        self.__dict__.update(restored.__dict__)
