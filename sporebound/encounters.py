"""Bounded reinforcement scheduler for small tactical encounters.

Pending waves are FIFO and spawn only when capacity is available. A wave is
atomic: it is never partially inserted into the battle roster.
"""
from copy import deepcopy
from .model import require


class EncounterDirector:
    def __init__(self, max_active=14):
        require(type(max_active) is int and 1 <= max_active <= 100, "Invalid encounter cap")
        self.max_active = max_active
        self.pending = []
        self.serial = 0

    def queue(self, actors, *, lifetime=None):
        require(isinstance(actors, list) and bool(actors), "Wave needs actors")
        require(len(actors) <= self.max_active, "Wave exceeds encounter capacity")
        require(lifetime is None or type(lifetime) is int and lifetime > 0,
                "Invalid wave lifetime")
        self.serial += 1
        wave_id = f"wave_{self.serial}"
        self.pending.append({"id": wave_id, "actors": deepcopy(actors),
                             "lifetime": lifetime})
        return wave_id

    def dispatch(self, battle):
        """Attempt the oldest wave; do not reorder later waves past it."""
        if not self.pending:
            return []
        wave = self.pending[0]
        active = sum(u.alive for u in battle.units)
        if active + len(wave["actors"]) > self.max_active:
            return []
        spawned = battle.spawn_wave(wave["actors"], lifetime=wave["lifetime"],
                                    max_active=self.max_active)
        self.pending.pop(0)
        battle.emit("encounter_wave_dispatched", wave=wave["id"],
                    units=[u.id for u in spawned])
        return spawned

    def state(self):
        return {"max_active": self.max_active, "serial": self.serial,
                "pending": deepcopy(self.pending)}
