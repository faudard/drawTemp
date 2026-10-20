"""R71.A: bounded, in-process *experimental* connected-session contracts.

This module is deliberately not imported by GameSession or the Player. It has
no sockets, matchmaking, persistence of credentials, or shipping multiplayer
capability. A trusted host supplies game rules as a pure state reducer; the
canonical R25 FixedTickJournal owns the tick order and replay evidence.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import hmac
import json
import re
import secrets

from .fixed_clock import FixedTickJournal, MAX_TICKS, _digest
from .model import require

VERSION = 1
MAX_WIRE_BYTES = 4096
MAX_STATE_BYTES = 65536
MAX_ENTITIES = 32
MAX_FUTURE_TICKS = 8
MAX_COMMANDS_PER_TICK = 32
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}\Z")
_FIELDS = frozenset({"version", "type", "session", "player", "sequence",
                     "tick", "entity", "command"})


def _identifier(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON field")
        result[key] = value
    return result


def _deny_constant(value):
    raise ValueError("Non-finite JSON number")


def _portable(value, limit):
    """Return a detached, canonical JSON value, rejecting NaNs and excess size."""
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("Non-portable connected payload") from exc
    require(len(raw) <= limit, "Connected payload size exceeded")
    return json.loads(raw)


def _check_command(command, allowed_kinds):
    require(type(command) is dict and set(command) == {"kind", "args"},
            "Command must contain only kind and args")
    require(_identifier(command["kind"]) and command["kind"] in allowed_kinds,
            "Command kind is not allowed")
    args = command["args"]
    require(type(args) is dict and len(args) <= 12, "Invalid command arguments")
    for key, value in args.items():
        require(_identifier(key), "Invalid command argument name")
        require((type(value) is int and -32768 <= value <= 32767)
                or type(value) is bool
                or (type(value) is str and len(value) <= 128),
                "Command arguments must be bounded scalar values")
    return _portable(command, MAX_WIRE_BYTES)


def validate_message(value, allowed_kinds):
    """Strict v1 client-command envelope; callers must authenticate separately."""
    require(type(value) is dict and set(value) == _FIELDS,
            "Unexpected connected protocol fields")
    require(type(value["version"]) is int and value["version"] == VERSION
            and value["type"] == "command", "Unsupported connected protocol")
    require(all(_identifier(value[k]) for k in ("session", "player", "entity")),
            "Invalid connected identity")
    require(type(value["sequence"]) is int and 1 <= value["sequence"] <= 2**31 - 1,
            "Invalid connected sequence")
    require(type(value["tick"]) is int and 1 <= value["tick"] <= MAX_TICKS,
            "Invalid connected tick")
    _check_command(value["command"], allowed_kinds)
    return _portable(value, MAX_WIRE_BYTES)


def encode_message(value, allowed_kinds):
    """Produce canonical UTF-8 wire bytes, never a Python pickle."""
    checked = validate_message(value, allowed_kinds)
    return json.dumps(checked, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def decode_message(raw, allowed_kinds):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_WIRE_BYTES,
            "Invalid connected frame length")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates,
                          parse_constant=_deny_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ValueError("Malformed connected frame") from exc
    return validate_message(data, allowed_kinds)


def _check_owners(owners):
    require(type(owners) is dict and 1 <= len(owners) <= MAX_ENTITIES,
            "Connected lab requires 1..32 owned entities")
    require(all(_identifier(entity) and _identifier(player)
                for entity, player in owners.items()), "Invalid ownership registry")
    require(len(set(owners.values())) <= 2,
            "Connected lab supports at most two identities")
    return dict(sorted(owners.items()))


def _check_kinds(kinds):
    require(type(kinds) in (set, frozenset, list, tuple) and 1 <= len(kinds) <= 16,
            "Expected a bounded command allowlist")
    require(all(_identifier(kind) for kind in kinds) and len(set(kinds)) == len(kinds),
            "Invalid or duplicate command kinds")
    return frozenset(kinds)


class ConnectedLabSession:
    """Opt-in server-side harness. Not a network service or a second game engine.

    The reducer(state, tick, rows) is trusted game-side code; it must return a
    new JSON-serializable state. All client commands are checked for schema,
    sequence, connection status, tick window, and entity ownership *before*
    reaching that reducer. The host authenticates the initial connection out
    of band using a 16+ character ticket; reconnect rotates it.
    """

    def __init__(self, session_id, initial_state, owners, allowed_kinds, reducer,
                 *, tickets, seed=1, rate=30):
        require(_identifier(session_id), "Invalid connected session id")
        require(callable(reducer), "Connected state reducer is required")
        self.session_id = session_id
        self._owners = _check_owners(owners)
        self.allowed_kinds = _check_kinds(allowed_kinds)
        players = set(self._owners.values())
        require(type(tickets) is dict and set(tickets) == players
                and all(type(v) is str and len(v) >= 16 and len(v) <= 256
                        for v in tickets.values()) and len(set(tickets.values())) == len(tickets),
                "Invalid or shared out-of-band tickets")
        self._ticket_hashes = {p: hashlib.sha256(v.encode("utf-8")).digest()
                               for p, v in tickets.items()}
        self._connected = set()
        self._last_sequence = {p: 0 for p in players}
        self._last_target_tick = {p: 0 for p in players}
        self._reducer = reducer
        self._initial = _portable(initial_state, MAX_STATE_BYTES)
        self._state = deepcopy(self._initial)
        self.journal = FixedTickJournal(seed=seed, rate=rate)
        self._pending_count = {}

    def resume(self, player, ticket, *, last_tick=0):
        """Authenticate/reconnect locally; return a rotated secret once.

        The caller must use a secure transport and rate limits when integrating
        this harness into a real service. These are NOT provided by R71.A.
        """
        require(player in self._ticket_hashes and type(ticket) is str
                and len(ticket) <= 256,
                "Unknown session identity")
        candidate = hashlib.sha256(ticket.encode("utf-8")).digest()
        require(hmac.compare_digest(candidate, self._ticket_hashes[player]),
                "Invalid session credential")
        require(type(last_tick) is int and 0 <= last_tick <= self.journal.tick,
                "Invalid reconnect cursor")
        replacement = secrets.token_urlsafe(32)
        self._ticket_hashes[player] = hashlib.sha256(replacement.encode()).digest()
        self._connected.add(player)
        return {"ticket": replacement, "tick": self.journal.tick,
                "state": deepcopy(self._state), "digest": _digest(self._state)}

    def disconnect(self, player):
        require(player in self._ticket_hashes, "Unknown session identity")
        self._connected.discard(player)

    @property
    def owners(self):
        return deepcopy(self._owners)

    @property
    def tick(self):
        return self.journal.tick

    def snapshot(self):
        return {"tick": self.tick, "state": deepcopy(self._state),
                "digest": _digest(self._state)}

    def submit(self, wire_bytes):
        """Reject before queueing, without consuming client sequence on error."""
        message = decode_message(wire_bytes, self.allowed_kinds)
        player, tick = message["player"], message["tick"]
        require(message["session"] == self.session_id, "Wrong connected session")
        require(player in self._connected, "Connected identity is not active")
        require(self._owners.get(message["entity"]) == player,
                "Client does not own target entity")
        require(message["sequence"] == self._last_sequence[player] + 1,
                "Duplicate, skipped, or out-of-order client sequence")
        require(tick >= self._last_target_tick[player],
                "Client ticks may not move backward")
        require(self.tick < tick <= min(MAX_TICKS, self.tick + MAX_FUTURE_TICKS),
                "Stale or too-distant connected tick")
        require(self._pending_count.get(tick, 0) < MAX_COMMANDS_PER_TICK,
                "Tick command budget exceeded")
        command = {**message["command"], "entity": message["entity"],
                   "client_sequence": message["sequence"]}
        submitted = self.journal.submit(tick, player, command)
        self._last_sequence[player] = message["sequence"]
        self._last_target_tick[player] = tick
        self._pending_count[tick] = self._pending_count.get(tick, 0) + 1
        return submitted

    def step(self):
        """Reducer failures are atomic for this harness and its tick journal."""
        computed = []

        def apply(tick, commands):
            state = self._reducer(deepcopy(self._state), tick, deepcopy(commands))
            computed.append(_portable(state, MAX_STATE_BYTES))
            return computed[-1]

        self.journal.step(apply)
        self._state = computed[0]
        self._pending_count.pop(self.tick, None)
        return self.snapshot()

    def recording(self):
        """Deterministic evidence only: never persist connection credentials."""
        data = {"version": VERSION, "kind": "connected_lab_r71",
                "session": self.session_id, "owners": deepcopy(self._owners),
                "allowed_kinds": sorted(self.allowed_kinds),
                "initial_digest": _digest(self._initial),
                "journal": self.journal.recording(),
                "final_digest": _digest(self._state)}
        return {**data, "digest": _digest(data)}

    @classmethod
    def replay(cls, recording, initial_state, reducer):
        """Reproduce server outcomes with the *same trusted* reducer/rules.

        SHA-256 detects accidental corruption, not hostile server forgery.
        """
        require(type(recording) is dict and set(recording) == {
            "version", "kind", "session", "owners", "allowed_kinds",
            "initial_digest", "journal", "final_digest", "digest"},
            "Malformed connected recording")
        data = {k: v for k, v in recording.items() if k != "digest"}
        require(recording["version"] == VERSION
                and recording["kind"] == "connected_lab_r71"
                and _identifier(recording["session"]), "Unsupported connected recording")
        require(type(recording["digest"]) is str
                and hmac.compare_digest(recording["digest"], _digest(data)),
                "Connected recording checksum mismatch")
        owners = _check_owners(recording["owners"])
        kinds = _check_kinds(recording["allowed_kinds"])
        require(recording["allowed_kinds"] == sorted(kinds),
                "Noncanonical connected command registry")
        state = _portable(initial_state, MAX_STATE_BYTES)
        require(recording["initial_digest"] == _digest(state),
                "Connected replay starting state differs")
        require(callable(reducer), "Connected replay reducer is required")
        seq = {p: 0 for p in owners.values()}
        # Inspect every input before invoking any world-side reducer.
        require(type(recording["journal"]) is dict
                and type(recording["journal"].get("inputs")) is list,
                "Invalid connected replay journal")
        rows = recording["journal"]["inputs"]
        require(type(rows) is list, "Invalid connected replay inputs")
        tick_by_player = {p: 0 for p in owners.values()}
        for row in rows:
            require(type(row) is dict and type(row.get("command")) is dict,
                    "Invalid connected recorded command")
            command, player = row["command"], row.get("source")
            require(set(command) == {"kind", "args", "entity", "client_sequence"}
                    and _identifier(command["entity"])
                    and owners.get(command["entity"]) == player,
                    "Unauthorized connected recorded command")
            _check_command({"kind": command["kind"], "args": command["args"]}, kinds)
            require(type(command["client_sequence"]) is int
                    and command["client_sequence"] == seq[player] + 1,
                    "Noncanonical connected recorded sequence")
            require(type(row.get("tick")) is int
                    and row["tick"] >= tick_by_player[player],
                    "Client input ticks moved backward in replay")
            tick_by_player[player] = row["tick"]
            seq[player] = command["client_sequence"]

        def apply(tick, commands):
            nonlocal state
            proposed = reducer(deepcopy(state), tick, deepcopy(commands))
            state = _portable(proposed, MAX_STATE_BYTES)
            return deepcopy(state)

        journal = FixedTickJournal.replay(recording["journal"], apply)
        require(_digest(state) == recording["final_digest"],
                "Connected final-state replay divergence")
        return {"tick": journal.tick, "state": deepcopy(state),
                "digest": _digest(state)}


__all__ = ["VERSION", "ConnectedLabSession", "encode_message", "decode_message",
           "validate_message"]
