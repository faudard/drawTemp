"""Global strategic clock for several simultaneous tactical fronts.

Inactive fronts resolve one deterministic strategic step at each synchronization.
The focused front is never auto-resolved. All fronts share one clock.
"""
from copy import deepcopy
from .model import require

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
    """Synchronize tactical battles with a single strategic timeline.

    Only the focused front accepts direct tactical commands. Switching occurs
    between strategic turns; inactive fronts use the aggregate FrontDirector.
    """

    def __init__(self, content, missions, focused, *, seed=1, rules=None, specs=None):
        from .engine import Battle
        require(isinstance(missions, dict) and missions and focused in missions,
                "Invalid multi-front missions")
        require(all(isinstance(mid, str) and mid in content.missions
                    for mid in missions.values()), "Unknown front mission")
        self.content = content
        self.missions = dict(missions)
        self.rules = rules
        self.seed = seed
        self.timeline = FrontDirector(
            specs or {name: {} for name in missions}, focused, seed=seed)
        self.battles = {}
        self.front_snapshots = {}
        self.pending_reinforcements = {}
        self.battles[focused] = Battle(content, missions[focused], seed=seed, rules=rules)

    @property
    def active(self):
        return self.battles[self.timeline.focused]

    def switch(self, front):
        from .engine import Battle
        require(front in self.missions, "Unknown front")
        require(self.active.active is None or self.active.active.moved is False
                and self.active.active.acted is False,
                "Finish the active unit turn before switching fronts")
        self.timeline.switch(front)
        if front in self.front_snapshots:
            # A previously simulated offscreen front is reopened at its latest
            # strategic checkpoint; it must not resume a stale tactical turn.
            self.front_snapshots.pop(front)
        if front not in self.battles:
            self.battles[front] = Battle(
                self.content, self.missions[front],
                seed=self.seed + sorted(self.missions).index(front), rules=self.rules)
        self._deliver_reinforcements(front)
        return self.active

    def reinforce(self, front, actors, *, lifetime=None):
        """Queue concrete actors for a front, even if its battle is not yet loaded."""
        require(front in self.missions and self.timeline.fronts[front]["status"] == "active",
                "Unknown or inactive reinforcement front")
        require(isinstance(actors, list) and bool(actors), "Reinforcements need actors")
        self.pending_reinforcements.setdefault(front, []).append(
            {"actors": deepcopy(actors), "lifetime": lifetime})
        self.timeline.events.append({"turn": self.timeline.turn, "kind": "reinforcement_queued",
                                     "front": front, "count": len(actors)})

    def _deliver_reinforcements(self, front):
        battle = self.battles[front]
        waves = self.pending_reinforcements.pop(front, [])
        for wave in waves:
            battle.queue_wave(wave["actors"], lifetime=wave["lifetime"])

    def advance(self):
        """Advance the strategic clock once, then reconcile finished tactical fronts."""
        for name, battle in self.battles.items():
            if battle.result in {"victory", "defeat"}:
                self.timeline.fronts[name]["status"] = battle.result
        before = deepcopy(self.timeline.fronts)
        state = self.timeline.advance()
        self._deliver_reinforcements(self.timeline.focused)
        for name, battle in self.battles.items():
            if name == self.timeline.focused or battle.result is not None:
                continue
            old, new = before[name], self.timeline.fronts[name]
            if old["status"] != "active":
                continue
            # Aggregate strategic losses become actual tactical HP losses.
            # Apply in stable unit order; never resurrect or reposition units.
            self._apply_attrition(battle, "player",
                                  old["strength"] - new["strength"])
            self._apply_attrition(battle, "enemy",
                                  old["opposition"] - new["opposition"])
            if new["status"] == "victory":
                self._apply_attrition(battle, "enemy", 1000000)
                battle.result = "victory"
            elif new["status"] == "defeat":
                self._apply_attrition(battle, "player", 1000000)
                battle.result = "defeat"
        for name, front in self.timeline.fronts.items():
            if name != self.timeline.focused and name in self.battles:
                self.front_snapshots[name] = deepcopy(front)
        return state

    @staticmethod
    def _apply_attrition(battle, team, amount):
        """Distribute offscreen HP loss without changing the initiative clock."""
        remaining = max(0, amount)
        for unit in sorted((u for u in battle.units if u.team == team and u.alive),
                           key=lambda u: u.id):
            if remaining == 0:
                break
            damage = min(unit.hp, remaining)
            unit.hp -= damage
            remaining -= damage

    def restore(self, state):
        """Restore strategic data; tactical battles must be reconstructed separately.

        Reject mismatched missions rather than silently mixing unrelated fronts.
        """
        require(isinstance(state, dict) and state.get("missions") == self.missions,
                "Incompatible multi-front save")
        require(isinstance(state.get("front_snapshots", {}), dict),
                "Invalid front checkpoints")
        self.timeline.restore(state["timeline"])
        self.front_snapshots = deepcopy(state.get("front_snapshots", {}))
        self.pending_reinforcements = deepcopy(state.get("pending_reinforcements", {}))
        # Battle.state() is a public snapshot, not a deserializer. Do not
        # pretend to restore live combat objects from it.
        require(not state.get("battles"), "Tactical battle restoration requires replay")

    def state(self):
        return {"timeline": self.timeline.state(), "missions": dict(self.missions),
                "battles": {name: battle.state() for name, battle in self.battles.items()},
                "front_snapshots": deepcopy(self.front_snapshots),
                "pending_reinforcements": deepcopy(self.pending_reinforcements)}
