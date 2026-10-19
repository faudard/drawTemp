"""R25 fixed-step input journal: integer ticks, stable ordering, verifiable replay.

This is a headless timing primitive, not a second world or tactical engine.
The owner (GameSession in a future integration) supplies a transactional
`handler(tick, commands) -> JSON-serializable world snapshot`. Rendering time
and wall-clock deltas never enter this contract.
"""
from copy import deepcopy
from hashlib import sha256
import json

from .model import require

VERSION = 1
MAX_TICKS = 100_000
MAX_INPUTS = 100_000


def _json_clone(value):
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                             allow_nan=False, separators=(",", ":"))
        return json.loads(encoded)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Non-portable tick payload: {exc}") from exc


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         allow_nan=False, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


class FixedTickJournal:
    """Queue inputs for future ticks and record snapshots after each fixed step.

    Ordering is (tick, source, submission_sequence), stable across platforms.
    A failed callback leaves journal state unchanged; the caller must roll
    back its external world transaction before retrying.
    """

    def __init__(self, *, rate=60, seed=1):
        require(type(rate) is int and rate in {20, 30, 60, 120},
                "Unsupported fixed tick rate")
        require(type(seed) is int and 0 <= seed <= 0xFFFFFFFF,
                "Invalid deterministic seed")
        self.rate, self.seed, self.tick = rate, seed, 0
        self._next_sequence = 0
        self._pending = []
        self._events = []
        self._states = []

    def submit(self, tick, source, command):
        require(type(tick) is int and self.tick < tick <= MAX_TICKS,
                "Input must target a future integer tick")
        require(type(source) is str and 0 < len(source) <= 64
                and all(c.isalnum() or c in "_-" for c in source),
                "Invalid input source")
        require(type(command) is dict and type(command.get("kind")) is str
                and 0 < len(command["kind"]) <= 64,
                "Command requires a kind")
        require(len(self._events) + len(self._pending) < MAX_INPUTS,
                "Tick journal input limit reached")
        payload = _json_clone(command)
        event = {"tick": tick, "source": source,
                 "sequence": self._next_sequence, "command": payload}
        self._next_sequence += 1
        self._pending.append(event)
        return deepcopy(event)

    def step(self, handler):
        require(callable(handler), "Tick handler must be callable")
        require(self.tick < MAX_TICKS, "Tick journal duration limit reached")
        target = self.tick + 1
        current = sorted((row for row in self._pending if row["tick"] == target),
                         key=lambda row: (row["source"], row["sequence"]))
        # Only a successful handler + serializable snapshot commits the tick.
        # Do not mutate the external state before validating the commands.
        snapshot = _json_clone(handler(target, deepcopy(current)))
        checksum = _digest(snapshot)
        self._pending = [row for row in self._pending if row["tick"] != target]
        self._events.extend(current)
        self._states.append(checksum)
        self.tick = target
        return snapshot

    def recording(self):
        require(not self._pending,
                "Cannot checkpoint with scheduled but unprocessed inputs")
        body = {
            "version": VERSION, "kind": "fixed_tick_journal",
            "rate": self.rate, "seed": self.seed, "tick": self.tick,
            "inputs": deepcopy(self._events), "states": list(self._states),
        }
        return {**body, "digest": _digest(body)}

    @classmethod
    def replay(cls, recording, handler):
        """Re-execute every tick and reject any checksum or state divergence.

        The handler must operate on a *fresh* world created using the same
        authored content and seed. No checkpoint migration is implicit.
        """
        require(type(recording) is dict and set(recording) ==
                {"version", "kind", "rate", "seed", "tick", "inputs",
                 "states", "digest"}, "Malformed fixed tick recording")
        require(type(recording["version"]) is int
                and recording["version"] == VERSION
                and recording["kind"] == "fixed_tick_journal",
                "Unsupported fixed tick recording")
        require(type(recording["tick"]) is int
                and 0 <= recording["tick"] <= MAX_TICKS
                and type(recording["states"]) is list
                and len(recording["states"]) == recording["tick"]
                and all(type(d) is str and len(d) == 64
                        for d in recording["states"]),
                "Invalid fixed tick state history")
        require(type(recording["inputs"]) is list
                and len(recording["inputs"]) <= MAX_INPUTS,
                "Invalid fixed tick input history")
        body = {k: v for k, v in recording.items() if k != "digest"}
        require(type(recording["digest"]) is str
                and recording["digest"] == _digest(body),
                "Fixed tick recording checksum mismatch")
        journal = cls(rate=recording["rate"], seed=recording["seed"])
        sequence_ids = set()
        prior_key = None
        for row in recording["inputs"]:
            require(type(row) is dict and set(row) ==
                    {"tick", "source", "sequence", "command"},
                    "Invalid recorded input")
            seq = row["sequence"]
            require(type(seq) is int and seq >= 0 and seq not in sequence_ids,
                    "Duplicate/invalid submission sequence")
            require(type(row["tick"]) is int
                    and 1 <= row["tick"] <= recording["tick"],
                    "Invalid recorded tick")
            require(type(row["source"]) is str and bool(row["source"])
                    and len(row["source"]) <= 64
                    and all(c.isalnum() or c in "_-" for c in row["source"]),
                    "Invalid recorded source")
            require(type(row["command"]) is dict
                    and type(row["command"].get("kind")) is str
                    and 0 < len(row["command"]["kind"]) <= 64,
                    "Invalid recorded command")
            ordering = (row["tick"], row["source"], seq)
            require(prior_key is None or prior_key < ordering,
                    "Recorded inputs are not in canonical order")
            prior_key = ordering
            sequence_ids.add(seq)
            journal._pending.append(_json_clone(row))
        journal._next_sequence = max(sequence_ids, default=-1) + 1
        for expected in recording["states"]:
            journal.step(handler)
            require(journal._states[-1] == expected,
                    f"Fixed tick replay diverged at tick {journal.tick}")
        require(journal.recording() == recording,
                "Fixed tick replay journal does not match original")
        return journal


__all__ = ["FixedTickJournal"]
