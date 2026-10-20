"""R67 laboratory ONLY: deterministic authoritative two-player transport spike.

No sockets, authentication service, multiplayer SDK feature, persistence, or
integration with GameSession. No production networking is advertised.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from random import Random

PROTOCOL = 1
PLAYERS = ("p1", "p2")
SPAWNS = {"p1": (1, 1), "p2": (6, 4)}
WALLS = frozenset({(3, 2), (4, 2)})
MAX_TICKS = 1200
MAX_AHEAD = 16


class SpikeError(ValueError):
    """Rejected untrusted laboratory command or unsupported configuration."""


def _check(ok, reason):
    if not ok:
        raise SpikeError(reason)


def _hash(data):
    value = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(value.encode("ascii")).hexdigest()


def _int(value, low, high):
    return type(value) is int and low <= value <= high


def validate_command(packet, sender):
    """Exact allowlist. The transport-supplied identity cannot be spoofed."""
    _check(type(packet) is dict and set(packet) == {
        "version", "player", "tick", "seq", "dx", "dy"
    }, "invalid_schema")
    _check(packet["version"] == PROTOCOL and type(packet["version"]) is int,
           "unsupported_version")
    _check(sender in PLAYERS and packet["player"] == sender and
           type(packet["player"]) is str, "unauthorized_player")
    _check(_int(packet["tick"], 1, MAX_TICKS) and
           _int(packet["seq"], 1, MAX_TICKS) and
           _int(packet["dx"], -1, 1) and _int(packet["dy"], -1, 1) and
           abs(packet["dx"]) + abs(packet["dy"]) <= 1, "invalid_command")
    return deepcopy(packet)


class AuthoritativeLab:
    """Server owns all positions and journal; clients submit *intent* only."""

    def __init__(self):
        self.tick = 0
        self.positions = dict(SPAWNS)
        self.last_seq = dict.fromkeys(PLAYERS, 0)
        self.pending = {}
        self.journal = []

    def snapshot(self):
        positions = {name: list(self.positions[name]) for name in PLAYERS}
        state = {"version": PROTOCOL, "tick": self.tick, "positions": positions}
        return {**state, "digest": _hash(state)}

    def submit(self, sender, packet):
        command = validate_command(packet, sender)
        tick = command["tick"]
        _check(self.tick < tick <= min(MAX_TICKS, self.tick + MAX_AHEAD),
               "stale_or_future_tick")
        _check(command["seq"] > self.last_seq[sender], "replayed_sequence")
        _check(sender not in self.pending.get(tick, {}), "duplicate_tick")
        self.pending.setdefault(tick, {})[sender] = command
        self.last_seq[sender] = command["seq"]

    def advance(self):
        _check(self.tick < MAX_TICKS, "tick_budget_exceeded")
        self.tick += 1
        commands = self.pending.pop(self.tick, {})
        for player in PLAYERS:  # fixed tie-break, no client-chosen execution order
            command = commands.get(player)
            if command is None:
                continue
            x, y = self.positions[player]
            target = (x + command["dx"], y + command["dy"])
            if (0 <= target[0] < 8 and 0 <= target[1] < 6 and
                    target not in WALLS and
                    target not in (self.positions[p] for p in PLAYERS if p != player)):
                self.positions[player] = target
        row = {"tick": self.tick, "commands": [deepcopy(commands[p])
               for p in PLAYERS if p in commands], "digest": self.snapshot()["digest"]}
        self.journal.append(row)
        return self.snapshot()


def verify_journal(journal):
    """Fail closed: replay every accepted command from the fixed starting state."""
    _check(type(journal) is list and len(journal) <= MAX_TICKS, "invalid_journal")
    server = AuthoritativeLab()
    for row in journal:
        _check(type(row) is dict and set(row) == {"tick", "commands", "digest"}
               and row["tick"] == server.tick + 1 and type(row["tick"]) is int
               and type(row["commands"]) is list and len(row["commands"]) <= 2
               and type(row["digest"]) is str and len(row["digest"]) == 64,
               "invalid_journal_row")
        for packet in row["commands"]:
            _check(type(packet) is dict, "invalid_journal_command")
            server.submit(packet.get("player"), packet)
        _check(server.advance()["digest"] == row["digest"], "replay_diverged")
    return server.snapshot()["digest"]


class UnreliableLink:
    """Deterministic simulated datagrams; NEVER opens a real socket."""

    def __init__(self, seed, loss_percent, latency_ticks, jitter_ticks):
        self.rng = Random(seed)
        self.loss_percent = loss_percent
        self.latency_ticks = latency_ticks
        self.jitter_ticks = jitter_ticks
        self.queue = []
        self.sent = self.lost = 0

    def send(self, message, wall_tick):
        self.sent += 1
        if self.rng.randrange(100) < self.loss_percent:
            self.lost += 1
            return
        at = wall_tick + self.latency_ticks + self.rng.randrange(self.jitter_ticks + 1)
        self.queue.append((at, self.sent, deepcopy(message)))

    def receive(self, wall_tick):
        due, later = [], []
        for row in self.queue:
            (due if row[0] <= wall_tick else later).append(row)
        self.queue = later
        return [message for _, _, message in sorted(due)]


def run_spike(*, seed=67, ticks=240, loss_percent=8, latency_ticks=2,
              jitter_ticks=2, input_lead=5, snapshot_interval=4):
    """Reproducible two-player feasibility probe, no network/system side effects.

    Returns measurement data, not a production GO certification. Latency and
    jitter are measured in logical 60 Hz ticks (1 tick = 16.67 ms).
    """
    for name, value, lo, hi in (
        ("seed", seed, 0, 2**32 - 1), ("ticks", ticks, 1, MAX_TICKS),
        ("loss_percent", loss_percent, 0, 100),
        ("latency_ticks", latency_ticks, 0, 12),
        ("jitter_ticks", jitter_ticks, 0, 12),
        ("input_lead", input_lead, 0, MAX_AHEAD),
        ("snapshot_interval", snapshot_interval, 1, 30),
    ):
        _check(_int(value, lo, hi), "invalid_" + name)
    server = AuthoritativeLab()
    uplink = UnreliableLink(seed, loss_percent, latency_ticks, jitter_ticks)
    downlink = UnreliableLink(seed ^ 0x67A, loss_percent,
                              latency_ticks, jitter_ticks)
    observed = dict.fromkeys(PLAYERS, 0)
    drifts = []
    rejects = {}
    verified_snapshots = 0
    stale_snapshots = 0
    for wall in range(ticks):
        target_tick = wall + input_lead + 1
        if target_tick <= ticks:
            for player in PLAYERS:
                move = ((target_tick + (player == "p2")) % 4)
                dx, dy = ((1, 0), (0, 1), (-1, 0), (0, -1))[move]
                uplink.send((player, {"version": PROTOCOL, "player": player,
                             "tick": target_tick, "seq": target_tick,
                             "dx": dx, "dy": dy}), wall)
        for sender, packet in uplink.receive(wall):
            try:
                server.submit(sender, packet)
            except SpikeError as exc:
                rejects[str(exc)] = rejects.get(str(exc), 0) + 1
        snapshot = server.advance()
        if server.tick % snapshot_interval == 0 or server.tick == ticks:
            for player in PLAYERS:
                downlink.send((player, snapshot), wall)
        for player, received in downlink.receive(wall):
            state = {key: received[key] for key in ("version", "tick", "positions")}
            if received["digest"] != _hash(state):
                raise SpikeError("snapshot_corrupted")
            if received["digest"] != server.journal[received["tick"] - 1]["digest"]:
                raise SpikeError("authoritative_snapshot_diverged")
            if received["tick"] <= observed[player]:
                stale_snapshots += 1
            else:
                observed[player] = received["tick"]
                verified_snapshots += 1
        drifts.extend(server.tick - observed[player] for player in PLAYERS)
    # Flush already-sent datagrams WITHOUT advancing gameplay or silently
    # injecting a reliable final snapshot; remaining lag stays measurable.
    for player, received in downlink.receive(ticks + latency_ticks + jitter_ticks + 1):
        state = {key: received[key] for key in ("version", "tick", "positions")}
        _check(received["digest"] == _hash(state) and
               received["digest"] == server.journal[received["tick"] - 1]["digest"],
               "snapshot_corrupted")
        observed[player] = max(observed[player], received["tick"])
    ordered = sorted(drifts)
    return {
        "study": "R67.B", "simulation_only": True, "protocol": PROTOCOL,
        "config": {"seed": seed, "ticks": ticks, "loss_percent": loss_percent,
                   "latency_ticks": latency_ticks, "jitter_ticks": jitter_ticks,
                   "input_lead": input_lead, "snapshot_interval": snapshot_interval},
        "tick_hz": 60, "uplink_sent": uplink.sent, "uplink_lost": uplink.lost,
        "downlink_sent": downlink.sent, "downlink_lost": downlink.lost,
        "server_rejections": rejects, "verified_snapshots": verified_snapshots,
        "stale_snapshots": stale_snapshots,
        "max_drift_ticks": ordered[-1],
        "p95_drift_ticks": ordered[(len(ordered) * 95 + 99) // 100 - 1],
        "final_client_lag_ticks": {p: ticks - observed[p] for p in PLAYERS},
        "server_digest": server.snapshot()["digest"],
        "replay_verified": verify_journal(server.journal) == server.snapshot()["digest"],
        "decision": "REDUCE", "production_multiplayer_ready": False,
        "reason": "Simulation only; no authenticated transport, real devices or security audit",
    }
