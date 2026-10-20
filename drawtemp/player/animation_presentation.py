"""R36.B3 optional read-only R26 actor animation presentation binding.

Existing R28 sprite IDs, R36 state controllers, and B2 visual markers are
sampled only AFTER committed action ticks. A cue is not an attack/hit event.
No canonical replay or GameProject schemas change.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

from sporebound.action_runtime import TICK_HZ, SCALE
from sporebound.animation_graph import AnimationStateController, controllers_from_project
from sporebound.animation_timeline import timelines_from_project, cues_crossed
from sporebound.assets import AssetRegistry

MAX_ACTORS = 32
MAX_CUES = 96
CUE_LIFETIME = 9
CUE_FX_KIND = {"spark": "spark", "dust": "dust",
               "trail": "dust", "glow": "guard"}


class ActionAnimationPresentation:
    """Opt-in adapter; caller supplies explicit actor -> existing graph ID map.

    No state graph controls the simulation. Historical actions after checkpoint
    load are *not* reinterpreted; reset anchors presentation at restored tick.
    """

    def __init__(self, project, bindings, scene):
        source = project.to_dict() if hasattr(project, "to_dict") else project
        if type(source) is not dict or type(bindings) is not dict or not bindings:
            raise ValueError("Animation binding requires a project and actor map")
        valid_actors = {"hero"} | {row["id"] for row in scene["enemies"]}
        if (len(bindings) > MAX_ACTORS or
                any(type(actor) is not str or actor not in valid_actors or
                    type(cid) is not str for actor, cid in bindings.items())):
            raise ValueError("Animation bindings must reference known R26 actors")
        self.registry = AssetRegistry(source.get("assets") or None)
        available = {row["id"]: row for row in controllers_from_project(source)}
        timelines = {row["controller_id"]: row
                     for row in timelines_from_project(source)}
        if any(cid not in available for cid in bindings.values()):
            raise ValueError("Animation binding references unknown controller")
        self._specs = {
            actor: (available[cid], timelines.get(cid))
            for actor, cid in sorted(bindings.items())}
        self.reset()

    def reset(self, tick=0):
        if type(tick) is not int or tick < 0:
            raise ValueError("Cannot reset animation to an invalid tick")
        self.controllers = {
            actor: AnimationStateController(graph, self.registry)
            for actor, (graph, _) in self._specs.items()}
        self._frames = {}
        for actor, controller in self.controllers.items():
            controller.advance(tick)
            self._frames[actor] = controller.sample(tick)
        self._tick = tick
        self._cues = []

    def _events_for(self, actor, events):
        names = []
        for event in events:
            kind = event["kind"]
            subject = event.get("enemy", "hero")
            if actor == "hero":
                mapping = {"hero_attack": "attack", "hero_dodge": "dodge",
                           "hero_hit": "hit", "hero_dead": "death",
                           "guard": "guard"}
                if kind in mapping:
                    names.append(mapping[kind])
            elif subject == actor:
                mapping = {"enemy_hit": "hit", "enemy_dead": "death",
                           "enemy_attack": "attack"}
                if kind in mapping:
                    names.append(mapping[kind])
        return names

    def observe(self, snapshot, events):
        """Advance only on contiguous successful R26 ticks, atomically per actor."""
        tick = snapshot.get("tick")
        if (type(tick) is not int or tick != self._tick + 1
                or snapshot.get("tick_hz") != TICK_HZ or
                type(events) not in (list, tuple) or len(events) > 64 or
                any(type(row) is not dict or type(row.get("tick")) is not int or
                    row["tick"] != tick or
                    type(row.get("kind")) is not str for row in events)):
            raise ValueError("Animation binding expects committed consecutive R26 events")
        # Build a new immutable-from-caller state so a rejected visual graph
        # cannot partly advance one actor but leave another behind.
        proposed = {}
        frames = {}
        emitted = []
        for actor, (graph, timeline) in self._specs.items():
            original = self.controllers[actor]
            machine = AnimationStateController(
                graph, self.registry, checkpoint=original.checkpoint())
            old_state = machine.state
            old_entry = machine.entered_tick
            frame = machine.advance(tick, self._events_for(actor, events))
            frames[actor] = frame
            proposed[actor] = machine
            if timeline is None:
                continue
            if machine.state == old_state and machine.entered_tick == old_entry:
                interval_start = tick - 1
            else:
                # A new clip can emit its at_ms=0 visual cue this same tick.
                interval_start = tick - 1
            cue_rows = cues_crossed(
                timeline, graph, self.registry, state=machine.state,
                entered_tick=machine.entered_tick,
                from_tick=interval_start, to_tick=tick, tick_rate=TICK_HZ)
            entity = snapshot["hero"] if actor == "hero" else snapshot["enemies"].get(actor)
            if entity is None or type(entity.get("pos")) is not list:
                raise ValueError("Animation actor absent in authoritative snapshot")
            x, y = entity["pos"]
            for marker in cue_rows:
                emitted.append({
                    "id": "cue:" + actor + ":" + sha256(marker["id"].encode(
                        "utf-8")).hexdigest()[:16],
                    "kind": CUE_FX_KIND[marker["cue"]], "actor": actor,
                    "x": x / SCALE - .5, "y": y / SCALE - .5,
                    "born": tick, "expires": tick + CUE_LIFETIME,
                })
        self.controllers = proposed
        self._frames = frames
        self._tick = tick
        self._cues = (
            [row for row in self._cues if row["expires"] > tick] + emitted
        )[-MAX_CUES:]

    def frames(self):
        return deepcopy(self._frames)

    def cues(self):
        result = []
        for row in self._cues:
            lifespan = row["expires"] - row["born"]
            remaining = row["expires"] - self._tick
            result.append({
                "id": row["id"], "kind": row["kind"], "actor": row["actor"],
                "x": row["x"], "y": row["y"],
                "alpha": remaining / lifespan, "scale": 1.0,
            })
        return deepcopy(result)
