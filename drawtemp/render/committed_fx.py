"""R36.B1 — deterministic cosmetic effects from *committed* R26 events.

This is a bounded CPU/QML presentation fallback, not gameplay collision,
not a particle GPU benchmark and not a separate timeline clock. Effects
are stamped with the authoritative fixed 60 Hz simulation tick. No RNG.
"""
from __future__ import annotations

from copy import deepcopy
from sporebound.action_runtime import SCALE, TICK_HZ

MAX_EMITS_PER_TICK = 32
MAX_ACTIVE = 96
# kind -> (visual type, visual lifetime in logical ticks)
EVENT_FX = {
    "hero_attack": ("slash", 8),
    "hero_dodge": ("dust", 9),
    "enemy_hit": ("impact", 12),
    "hero_hit": ("impact", 12),
    "hero_dead": ("defeat", 25),
    "enemy_dead": ("defeat", 25),
    "guard": ("guard", 7),
    "interaction": ("spark", 10),
}


class CommittedFxDirector:
    """Read-only action-event projection with strict order and bounded lifetimes.

    Call observe() exactly once *after* ActionRuntime.step has succeeded.
    Rendering/snapshotting may happen any number of times without advancing
    simulation or creating effects. reset() is required on load/respawn.
    """

    def __init__(self):
        self.reset()

    def reset(self, tick=0):
        if type(tick) is not int or tick < 0:
            raise ValueError("FX reset requires a nonnegative simulation tick")
        self._tick = tick
        self._active = []

    def observe(self, snapshot, events):
        if (type(snapshot) is not dict or type(snapshot.get("tick")) is not int
                or snapshot["tick"] != self._tick + 1
                or snapshot.get("tick_hz") != TICK_HZ):
            raise ValueError("FX requires the next committed R26 snapshot")
        if type(events) not in (list, tuple) or len(events) > MAX_EMITS_PER_TICK:
            raise ValueError("FX event count exceeds the per-tick budget")
        tick = snapshot["tick"]
        # Validate every recognized event before changing state.
        emitted = []
        hero = snapshot["hero"]
        enemies = snapshot["enemies"]
        for index, event in enumerate(events):
            if (type(event) is not dict or type(event.get("tick")) is not int
                    or event["tick"] != tick or type(event.get("kind")) is not str):
                raise ValueError("FX event is not part of the committed tick")
            kind = event["kind"]
            if kind not in EVENT_FX:
                continue
            enemy_id = event.get("enemy")
            actor = "hero" if kind.startswith("hero_") or kind in (
                "guard", "interaction") else enemy_id
            if type(actor) is not str:
                raise ValueError("FX event has no valid actor")
            entity = hero if actor == "hero" else enemies.get(actor)
            if entity is None:
                raise ValueError("FX references an absent authoritative actor")
            pos = entity.get("pos")
            if (type(pos) is not list or len(pos) != 2 or
                    any(type(x) is not int for x in pos)):
                raise ValueError("FX actor has invalid authoritative coordinates")
            name, lifetime = EVENT_FX[kind]
            # Fractional cell centres, identical to R3 scene_from_action().
            emitted.append({
                "id": f"{tick}:{index}", "kind": name, "actor": actor,
                "x": pos[0] / SCALE - .5, "y": pos[1] / SCALE - .5,
                "born": tick, "expires": tick + lifetime,
            })
        self._active = (
            [row for row in self._active if row["expires"] > tick] + emitted
        )[-MAX_ACTIVE:]
        self._tick = tick
        return self.snapshot()

    def snapshot(self, *, reduced_flashes=False):
        if type(reduced_flashes) is not bool:
            raise ValueError("reduced_flashes must be boolean")
        result = []
        for row in self._active:
            if reduced_flashes and row["kind"] in ("impact", "spark"):
                continue
            lifetime = row["expires"] - row["born"]
            remaining = max(0, row["expires"] - self._tick)
            result.append({
                "id": row["id"], "kind": row["kind"], "actor": row["actor"],
                "x": row["x"], "y": row["y"],
                "alpha": remaining / lifetime,
                "scale": 0.7 + 0.3 * (1 - remaining / lifetime),
            })
        return deepcopy(result)
