"""R71.B experimental, in-process connected service and deterministic fault link.

Not a socket, public server, or production networking feature. Does not import
GameSession or touch offline save/replay formats. Only approved v1 command frames
are forwarded to the R71.A authoritative laboratory session.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
import random

from .connected_lab_r71 import (VERSION, MAX_WIRE_BYTES, _identifier,
                                decode_message)
from .model import require, RuleError

CAPABILITY = "commands_v1"
MAX_PENDING_PACKETS = 256
MAX_EVENTS = 128
MAX_SIM_STEPS = 10000


def validate_hello(hello):
    """Allow only compatible v1 clients; no implicit gameplay migration."""
    require(type(hello) is dict and set(hello) == {
        "version", "session", "player", "last_tick", "capabilities"},
        "Malformed connected client hello")
    require(type(hello["version"]) is int and hello["version"] == VERSION,
            "Unsupported client protocol version: upgrade required")
    require(_identifier(hello["session"]) and _identifier(hello["player"]),
            "Invalid connected client identity")
    require(type(hello["last_tick"]) is int and hello["last_tick"] >= 0,
            "Invalid client checkpoint tick")
    require(type(hello["capabilities"]) is list and
            hello["capabilities"] == [CAPABILITY],
            "Incompatible client command capabilities")
    return deepcopy(hello)


def plan_v0_hello_migration(legacy):
    """Pure upgrade suggestion for *handshake only*; not command conversion.

    Callers must explicitly confirm and deploy a v1 client before connecting.
    The server never automatically accepts a legacy client as v1.
    """
    require(type(legacy) is dict and set(legacy) == {
        "version", "session", "player", "cursor"} and
        type(legacy["version"]) is int and legacy["version"] == 0,
        "Not a supported legacy hello")
    proposal = {"version": VERSION, "session": legacy["session"],
                "player": legacy["player"], "last_tick": legacy["cursor"],
                "capabilities": [CAPABILITY]}
    validate_hello(proposal)
    return proposal


class ConnectedLabService:
    """Synchronous service interface; all authentication remains out of band."""

    def __init__(self, laboratory):
        require(hasattr(laboratory, "resume") and hasattr(laboratory, "submit")
                and hasattr(laboratory, "journal") and hasattr(laboratory, "step")
                and hasattr(laboratory, "allowed_kinds"),
                "Expected an R71.A connected laboratory")
        self._lab = laboratory
        self._negotiated = set()
        self._counts = {name: 0 for name in (
            "handshake_accepted", "handshake_rejected", "frames_accepted",
            "frames_rejected", "ticks_advanced", "disconnections")}
        self._events = deque(maxlen=MAX_EVENTS)

    @property
    def tick(self):
        return self._lab.tick

    def _track(self, category, code):
        self._counts[category] += 1
        # Intentionally do not log frames, player names, secrets or state.
        self._events.append({"tick": self.tick, "code": code})

    def connect(self, hello, ticket):
        # Reject protocol mismatch BEFORE checking credentials or changing state.
        try:
            validated = validate_hello(hello)
            require(validated["session"] == self._lab.session_id,
                    "Connected session mismatch")
            response = self._lab.resume(validated["player"], ticket,
                                        last_tick=validated["last_tick"])
        except (RuleError, ValueError):
            self._track("handshake_rejected", "INCOMPATIBLE_OR_DENIED")
            raise
        self._negotiated.add(validated["player"])
        self._track("handshake_accepted", "NEGOTIATED_V1")
        # Ticket is returned ONLY to authenticated caller; never to diagnostics.
        return {"version": VERSION, "capability": CAPABILITY, **response}

    def disconnect(self, player):
        self._lab.disconnect(player)
        self._negotiated.discard(player)
        self._track("disconnections", "DISCONNECTED")

    def receive(self, frame):
        """Never echo client payload or sensitive identities in responses."""
        try:
            message = decode_message(frame, self._lab.allowed_kinds)
        except (RuleError, ValueError):
            code = "MALFORMED_FRAME"
        else:
            if message["player"] not in self._negotiated:
                code = "HANDSHAKE_REQUIRED"
            else:
                try:
                    self._lab.submit(frame)
                except (RuleError, ValueError):
                    code = "COMMAND_REJECTED"
                else:
                    self._track("frames_accepted", "FRAME_ACCEPTED")
                    return {"accepted": True, "code": "FRAME_ACCEPTED",
                            "server_tick": self.tick}
        self._track("frames_rejected", code)
        return {"accepted": False, "code": code, "server_tick": self.tick}

    def advance(self):
        # Failed reducers commit neither the tick nor its diagnostics.
        snapshot = self._lab.step()
        self._track("ticks_advanced", "TICK_ADVANCED")
        return snapshot

    def diagnostics(self):
        return {"format": "r71b-service-metrics-v1", "tick": self.tick,
                "counts": deepcopy(self._counts),
                "recent_events": [dict(row) for row in self._events]}

    def snapshot(self):
        return self._lab.snapshot()

    def recording(self):
        return self._lab.recording()


@dataclass(frozen=True)
class FaultProfile:
    """Deterministic network parameters; all percentages in [0, 100]."""
    latency_steps: int = 1
    jitter_steps: int = 0
    drop_percent: int = 0
    duplicate_percent: int = 0
    reorder_every: int = 0
    reorder_extra_steps: int = 0

    def __post_init__(self):
        for key in ("latency_steps", "jitter_steps", "drop_percent",
                    "duplicate_percent", "reorder_every", "reorder_extra_steps"):
            require(type(getattr(self, key)) is int, "Invalid fault profile type")
        require(1 <= self.latency_steps <= 32 and 0 <= self.jitter_steps <= 32,
                "Invalid latency simulation bound")
        require(0 <= self.drop_percent <= 100 and
                0 <= self.duplicate_percent <= 100,
                "Invalid packet fault probability")
        require((self.reorder_every == 0 or 2 <= self.reorder_every <= 32) and
                0 <= self.reorder_extra_steps <= 32 and
                (self.reorder_every == 0 or self.reorder_extra_steps > 0),
                "Invalid packet reordering schedule")


class SimulatedSessionLink:
    """Seeded fault-injection link: no sockets, timers or client thread."""

    def __init__(self, service, profile=None, *, seed=1):
        require(isinstance(service, ConnectedLabService),
                "A local connected service is required")
        require(profile is None or isinstance(profile, FaultProfile),
                "Invalid network profile")
        require(type(seed) is int and 0 <= seed <= 0xFFFFFFFF,
                "Invalid simulator seed")
        self.service = service
        self.profile = profile if profile is not None else FaultProfile()
        self._random = random.Random(seed)
        self._seed = seed
        self._step = 0
        self._sent = 0
        self._pending = []
        self._largest_delivered = 0
        self._latencies = deque(maxlen=MAX_EVENTS)
        self._counts = {name: 0 for name in (
            "sent", "dropped", "duplicated", "delivered", "reordered",
            "accepted", "rejected")}

    def send(self, frame):
        require(type(frame) is bytes and 0 < len(frame) <= MAX_WIRE_BYTES,
                "Invalid simulated transport frame")
        require(self._sent < 100000, "Simulated transport input limit reached")
        next_id = self._sent + 1
        random_state = self._random.getstate()
        lost = self._random.randrange(100) < self.profile.drop_percent
        duplicate = (not lost and
                     self._random.randrange(100) < self.profile.duplicate_percent)
        copies = 0 if lost else 1 + int(duplicate)
        if len(self._pending) + copies > MAX_PENDING_PACKETS:
            self._random.setstate(random_state)
            raise RuleError("Simulated transport queue is full")
        self._sent = next_id
        self._counts["sent"] += 1
        if lost:
            self._counts["dropped"] += 1
            return next_id
        if duplicate:
            self._counts["duplicated"] += 1
        delay = (self.profile.latency_steps +
                 self._random.randint(0, self.profile.jitter_steps))
        # Deterministically delay the first member of each N-frame group;
        # later frames can overtake it when reordering is enabled.
        if (self.profile.reorder_every > 1 and
                next_id % self.profile.reorder_every == 1):
            delay += self.profile.reorder_extra_steps
        for copy_no in range(copies):
            self._pending.append({"id": next_id, "copy": copy_no,
                                  "sent_at": self._step,
                                  "due": self._step + delay,
                                  "frame": bytes(frame)})
        return next_id

    def pump(self, steps=1):
        """Advance virtual link time. Caller advances game ticks separately."""
        require(type(steps) is int and 1 <= steps <= 256 and
                self._step + steps <= MAX_SIM_STEPS,
                "Invalid simulated network duration")
        received = []
        for _ in range(steps):
            self._step += 1
            ready = sorted((p for p in self._pending if p["due"] <= self._step),
                           key=lambda p: (p["due"], p["id"], p["copy"]))
            self._pending = [p for p in self._pending if p["due"] > self._step]
            for packet in ready:
                if packet["copy"] == 0:
                    if packet["id"] < self._largest_delivered:
                        self._counts["reordered"] += 1
                    self._largest_delivered = max(self._largest_delivered,
                                                  packet["id"])
                result = self.service.receive(packet["frame"])
                self._counts["delivered"] += 1
                self._counts["accepted" if result["accepted"] else "rejected"] += 1
                self._latencies.append(self._step - packet["sent_at"])
                received.append({"packet": packet["id"], "copy": packet["copy"],
                                 "network_step": self._step, "result": result})
        return received

    def diagnostics(self):
        values = sorted(self._latencies)
        p95 = values[(95 * len(values) + 99) // 100 - 1] if values else None
        return {"format": "r71b-fault-link-metrics-v1", "seed": self._seed,
                "network_step": self._step, "pending": len(self._pending),
                "counts": dict(self._counts), "latency_steps": {
                    "min": values[0] if values else None,
                    "max": values[-1] if values else None, "p95": p95}}


__all__ = ["CAPABILITY", "ConnectedLabService", "FaultProfile",
           "SimulatedSessionLink", "validate_hello", "plan_v0_hello_migration"]
