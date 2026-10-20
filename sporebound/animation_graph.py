"""R36.A: versioned *presentation* animation state graph over R28 AssetRegistry.

An animation marker is not a combat event. The caller must supply committed
R1/R26/R32 events; this controller never changes hitboxes, HP, RNG or saves.
The only clock is the caller's integer simulation tick (no wall-clock sampling).
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import re

from sporebound.assets import AssetRegistry

NAMESPACE = "org.drawtemp.animation"
SCHEMA_VERSION = 1
MAX_STATES = 48
MAX_TRANSITIONS = 128
_ID = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class AnimationGraphError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _fail(code, reason):
    raise AnimationGraphError(code, reason)


def _id(value, field):
    if type(value) is not str or _ID.fullmatch(value) is None:
        _fail("invalid_id", field + " must be a lowercase portable identifier")


def _shape(row, keys, field):
    if type(row) is not dict or set(row) != set(keys):
        _fail("invalid_shape", field + " has missing or unexpected fields")


def validate_controller(document, registry):
    """Validate a detached graph and its references to the *existing* R28 assets."""
    _shape(document, ("schema_version", "id", "initial", "states", "transitions"),
           "animation controller")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        _fail("unsupported_schema", "Explicit migration is required")
    _id(document["id"], "controller ID")
    if type(document["states"]) is not list or not 1 <= len(document["states"]) <= MAX_STATES:
        _fail("state_budget", "An animation controller needs 1..48 states")
    if (type(document["transitions"]) is not list or
            len(document["transitions"]) > MAX_TRANSITIONS):
        _fail("transition_budget", "Maximum 128 transitions")
    if not isinstance(registry, AssetRegistry):
        registry = AssetRegistry(registry)
    states = {}
    for state in document["states"]:
        _shape(state, ("id", "animation"), "state")
        _id(state["id"], "state ID")
        if state["id"] in states:
            _fail("duplicate_state", "Duplicate state: " + state["id"])
        if type(state["animation"]) is not str:
            _fail("unknown_animation", "Animation ID must be a string")
        try:
            registry.require_reference(state["animation"], "animation")
        except ValueError as exc:
            _fail("unknown_animation", str(exc))
        states[state["id"]] = state["animation"]
    if type(document["initial"]) is not str or document["initial"] not in states:
        _fail("invalid_initial", "Initial state does not exist")
    keys = set()
    for edge in document["transitions"]:
        _shape(edge, ("source", "target", "on", "priority"), "transition")
        if (type(edge["source"]) is not str or type(edge["target"]) is not str or
                edge["source"] not in states or edge["target"] not in states):
            _fail("unknown_state", "Transition refers to an unknown state")
        _id(edge["on"], "event name")
        if type(edge["priority"]) is not int or not 0 <= edge["priority"] <= 100:
            _fail("invalid_priority", "Priority must be an integer 0..100")
        key = (edge["source"], edge["on"], edge["priority"])
        if key in keys:
            _fail("ambiguous_transition",
                  "Two transitions have the same source, event and priority")
        keys.add(key)
    return deepcopy(document)


def _digest(document):
    return sha256(json.dumps(document, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True).encode("utf-8")).hexdigest()


class AnimationStateController:
    """Tick-addressed state selection; strictly read-only over the game simulation.

    Updates accept *committed* event names. The 'finished' event is derived from
    the animation's own frame duration, never from a gameplay hitbox window.
    Presentation sampling does not advance the machine or modify the registry.
    """

    def __init__(self, document, registry, *, checkpoint=None):
        self.registry = registry if isinstance(registry, AssetRegistry) else AssetRegistry(registry)
        self.graph = validate_controller(document, self.registry)
        self._animations = {
            state["id"]: self.registry.require_reference(state["animation"], "animation")
            for state in self.graph["states"]
        }
        self._transitions = sorted(self.graph["transitions"],
                                   key=lambda edge: -edge["priority"])
        self.state = self.graph["initial"]
        self.entered_tick = 0
        self.last_tick = -1
        if checkpoint is not None:
            self.restore(checkpoint)

    def _elapsed_ms(self, tick, tick_rate):
        return (tick - self.entered_tick) * 1000 // tick_rate

    def _duration(self):
        return sum(frame["duration_ms"] for frame in self._animations[self.state]["frames"])

    def advance(self, tick, events=(), *, tick_rate=60):
        if type(tick) is not int or tick < 0 or tick <= self.last_tick:
            _fail("invalid_tick", "Simulation ticks must increase strictly")
        if type(tick_rate) is not int or not 1 <= tick_rate <= 240:
            _fail("invalid_rate", "Tick rate must be 1..240")
        if type(events) not in (list, tuple) or len(events) > 32:
            _fail("invalid_events", "Expected at most 32 committed events")
        if any(type(event) is not str or not _ID.fullmatch(event) for event in events):
            _fail("invalid_events", "Event names must be portable identifiers")
        due = (not self._animations[self.state]["loop"] and
               self._elapsed_ms(tick, tick_rate) >= self._duration())
        candidates = set(events)
        if due:
            candidates.add("finished")
        # Exactly one transition per tick; stable order also for input permutations.
        eligible = [edge for edge in self._transitions if
                    edge["source"] == self.state and edge["on"] in candidates]
        if eligible:
            chosen = eligible[0]
            # A graph with equally ranked transitions for distinct events
            # requires an explicit authoring priority, not input-list order.
            if len(eligible) > 1 and eligible[1]["priority"] == chosen["priority"]:
                _fail("ambiguous_events", "Multiple equally prioritised events in one tick")
            self.state = chosen["target"]
            self.entered_tick = tick
        self.last_tick = tick
        return self.sample(tick, tick_rate=tick_rate)

    def sample(self, tick, *, tick_rate=60):
        """Portable resolved sprite descriptor; never reads a PNG or mutates state."""
        if type(tick) is not int or tick < self.entered_tick:
            _fail("invalid_tick", "Cannot sample before the entered state")
        if type(tick_rate) is not int or not 1 <= tick_rate <= 240:
            _fail("invalid_rate", "Tick rate must be 1..240")
        animation = self._animations[self.state]
        total = self._duration()
        elapsed = self._elapsed_ms(tick, tick_rate)
        offset = elapsed % total if animation["loop"] else min(elapsed, total - 1)
        frame_index = 0
        for frame_index, frame in enumerate(animation["frames"]):
            if offset < frame["duration_ms"]:
                break
            offset -= frame["duration_ms"]
        frame = animation["frames"][frame_index]
        sprite = self.registry.require_reference(frame["sprite"], "sprite")
        return {"state": self.state, "animation": animation["id"],
                "frame_index": frame_index, "sprite": sprite["id"],
                "elapsed_ms": elapsed}

    def checkpoint(self):
        return {"schema_version": 1, "controller_id": self.graph["id"],
                "graph_sha256": _digest(self.graph),
                "state": self.state, "entered_tick": self.entered_tick,
                "last_tick": self.last_tick}

    def restore(self, checkpoint):
        _shape(checkpoint, ("schema_version", "controller_id", "graph_sha256",
                            "state", "entered_tick", "last_tick"), "checkpoint")
        if (type(checkpoint["schema_version"]) is not int or
                checkpoint["schema_version"] != 1 or
                checkpoint["controller_id"] != self.graph["id"] or
                checkpoint["graph_sha256"] != _digest(self.graph)):
            _fail("checkpoint_mismatch", "Controller identity/version has changed")
        if checkpoint["state"] not in self._animations:
            _fail("checkpoint_state", "Unknown checkpoint state")
        entered, last = checkpoint["entered_tick"], checkpoint["last_tick"]
        if (type(entered) is not int or type(last) is not int or
                not 0 <= entered <= max(last, 0)):
            _fail("checkpoint_tick", "Inconsistent checkpoint ticks")
        self.state, self.entered_tick, self.last_tick = (
            checkpoint["state"], entered, last)


MAX_CONTROLLERS = 16


def controllers_from_project(project):
    """Validate the canonical R36 extension (also called by GameProject.load)."""
    if hasattr(project, "to_dict"):
        project = project.to_dict()
    if type(project) is not dict:
        _fail("invalid_project", "Expected GameProject object")
    envelope = project.get("extensions", {}).get(NAMESPACE)
    if envelope is None:
        return []
    if (type(envelope) is not dict or
            set(envelope) != {"schema_version", "data", "references"} or
            type(envelope["schema_version"]) is not int or
            envelope["schema_version"] != 1 or
            envelope["references"] != [] or
            type(envelope["data"]) is not dict or
            set(envelope["data"]) != {"controllers"} or
            type(envelope["data"]["controllers"]) is not list):
        _fail("invalid_storage", "R36 extension needs explicit migration")
    controllers = envelope["data"]["controllers"]
    if len(controllers) > MAX_CONTROLLERS:
        _fail("controller_budget", "At most 16 animation controllers")
    registry = AssetRegistry(project.get("assets") or None)
    result = [validate_controller(row, registry) for row in controllers]
    identifiers = [row["id"] for row in result]
    if len(set(identifiers)) != len(identifiers):
        _fail("duplicate_controller", "Controller IDs must be unique")
    return result
