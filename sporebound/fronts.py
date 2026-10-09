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
