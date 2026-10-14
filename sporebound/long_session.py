"""R8.9-R8.12: opt-in, replay-checked long-session journal over SessionStore v2.

This module does not change GameSession v1, the tactical recording formats,
or existing PlayerController slots. A single process must own a store.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
from functools import wraps

from .session_lock import session_writer_lock
from .game_session import GameSession, digest
from .model import RuleError, require
from .persistence import SessionStore
from .storage import json_text, write_bytes, write_json

_SHA = re.compile(r"^[0-9a-f]{64}$")
# Only canonical GameSession commands may enter the replay log. Never eval
# untrusted method names or arbitrary object properties.
OPERATIONS = frozenset({
    "choose_story_option", "choose_tactical_story_option", "start_configured_siege",
    "explore_move", "explore_interact", "explore_wait", "explore_actor",
    "world_destination", "world_advance", "start_mission", "start_fronts",
    "execute", "switch_front", "advance_fronts", "set_doctrine",
    "select_route", "negotiate_front", "partial_front", "withdraw_front",
    "start_recovery", "abandon_recovery", "send_reserves", "transfer_units",
    "escort_convoy", "rescue_convoy", "ai_turn", "return_to_campaign",
    "abandon_encounter",
})


def exclusive_write(method):
    """Serialize long-session mutations across independent writers."""
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with session_writer_lock(self.store.path):
            return method(self, *args, **kwargs)
    return guarded


@dataclass(frozen=True)
class LongSessionStatus:
    session: GameSession
    source: str
    sequence: int
    applied: int
    degraded: bool = False


@dataclass(frozen=True)
class JournalResult:
    applied: bool
    value: object = None
    compacted: bool = False


class LongSessionStore:
    """Full replay checkpoints plus bounded, atomic replay-command journals.

    Every operation is committed to a sidecar before an optional checkpoint.
    During compaction the journal is *not* truncated until the new full
    checkpoint is published: reopening either side of that boundary is safe.
    """

    VERSION = 1
    RECEIPTS = 128

    def __init__(self, path, *, checkpoint_every=32, max_journal_bytes=8 * 1024 * 1024):
        require(type(checkpoint_every) is int and 1 <= checkpoint_every <= 256,
                "Invalid checkpoint interval")
        require(type(max_journal_bytes) is int and 1024 <= max_journal_bytes <= 64 * 1024 * 1024,
                "Invalid journal size limit")
        self.store = SessionStore(path)
        self.journal = self.store.path.with_name(self.store.path.name + ".journal")
        self.checkpoint_every = checkpoint_every
        self.max_journal_bytes = max_journal_bytes

    def _empty(self, anchor, receipts=()):
        obj = {"kind": "long_session_journal", "version": self.VERSION,
               "base": anchor, "head": anchor, "entries": [],
               "receipts": list(receipts)[-self.RECEIPTS:]}
        obj["digest"] = digest(obj)
        return obj

    def _publish(self, obj):
        obj = {key: value for key, value in obj.items() if key != "digest"}
        obj["digest"] = digest(obj)
        require(len(json_text(obj).encode("utf-8")) <= self.max_journal_bytes,
                "Long-session journal exceeds size limit; compact first")
        write_json(self.journal, obj)

    def _read_journal(self):
        if not self.journal.exists():
            return None
        try:
            require(self.journal.stat().st_size <= self.max_journal_bytes,
                    "Long-session journal exceeds size limit")
            obj = json.loads(self.journal.read_text(encoding="utf-8"))
            require(isinstance(obj, dict) and
                    set(obj) == {"kind", "version", "base", "head", "entries", "receipts", "digest"} and
                    obj["kind"] == "long_session_journal" and
                    type(obj["version"]) is int and obj["version"] == self.VERSION,
                    "Unsupported long-session journal")
            for key in ("base", "head", "digest"):
                require(isinstance(obj[key], str) and _SHA.fullmatch(obj[key]),
                        "Invalid journal checksum")
            require(digest({k: v for k, v in obj.items() if k != "digest"}) == obj["digest"],
                    "Long-session journal checksum mismatch")
            require(isinstance(obj["entries"], list) and
                    len(obj["entries"]) <= self.checkpoint_every,
                    "Invalid long-session journal length")
            require(isinstance(obj["receipts"], list) and
                    len(obj["receipts"]) <= self.RECEIPTS and
                    all(isinstance(s, str) and 0 < len(s) <= 128 for s in obj["receipts"]) and
                    len(set(obj["receipts"])) == len(obj["receipts"]),
                    "Invalid operation receipts")
            previous = obj["base"]
            seen = set(obj["receipts"])
            for step in obj["entries"]:
                require(isinstance(step, dict) and
                        set(step) in ({"request_id", "operation", "args", "kwargs", "before", "after"},
                                      {"request_id", "operation", "args", "kwargs", "before", "after", "snapshot"}) and
                        isinstance(step["request_id"], str) and
                        0 < len(step["request_id"]) <= 128 and
                        step["request_id"] not in seen and
                        step["operation"] in OPERATIONS and
                        isinstance(step["args"], list) and
                        isinstance(step["kwargs"], dict) and
                        step["before"] == previous and
                        isinstance(step["after"], str) and _SHA.fullmatch(step["after"]),
                        "Invalid operation journal chain")
                seen.add(step["request_id"])
                previous = step["after"]
            require(obj["head"] == previous, "Journal head is inconsistent")
            return obj
        except (OSError, UnicodeError, ValueError, TypeError, KeyError,
                RecursionError, AttributeError) as exc:
            raise RuleError(f"Invalid long-session journal: {exc}") from exc

    @staticmethod
    def _replay(snapshot, entries, content, project, *, rules=None):
        current = snapshot
        for index, step in enumerate(entries):
            require(current.recording()["digest"] == step["before"],
                    f"Replay diverged before operation {index}")
            try:
                if "snapshot" in step:
                    # Battle creation may allocate a UUID. A fully validated
                    # canonical replay snapshot is the portable boundary for
                    # such an operation; never fabricate an arbitrary UUID.
                    current = GameSession.from_recording(
                        step["snapshot"], content, project, rules=rules)
                else:
                    getattr(current, step["operation"])(*step["args"], **step["kwargs"])
                record = current.recording()
                require(record["digest"] == step["after"],
                        f"Replay diverged after operation {index}")
            except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
                raise RuleError(f"Invalid replay operation {index}: {exc}") from exc
        # Verify independent reconstruction, including multi-front journals,
        # campaign rewards, reserves and all strategic event histories.
        record = current.recording()
        verified = GameSession.from_recording(record, content, project, rules=rules)
        require(verified.recording() == record, "Long-session replay diverged")
        return verified

    @exclusive_write
    def initialize(self, session):
        require(isinstance(session, GameSession), "Expected GameSession")
        damaged = self.store.path.with_name(self.store.path.name + ".damaged")
        require(not any(path.exists() for path in
                        (self.store.path, self.store.backup, self.journal, damaged)),
                "Long-session save or recovery evidence already exists; explicit migration required")
        record = session.recording()
        GameSession.from_recording(record, session.content, session.project,
                                   rules=session.rules)
        self.store.save(session)
        self._publish(self._empty(record["digest"]))
        return self.store.path

    def load_with_status(self, content, project, *, rules=None):
        journal = self._read_journal()
        errors = []
        for path, source in ((self.store.path, "primary"),
                             (self.store.backup, "backup")):
            if not path.exists():
                errors.append(f"{path.name}: missing")
                continue
            verified_file = False
            try:
                _, outcome = self.store._read(path, content, project, rules=rules)
                verified_file = True
                require(not outcome.migrated_from_v1,
                        "Migrate legacy v1 explicitly before using long sessions")
                record = outcome.session.recording()
                if journal is None:
                    return LongSessionStatus(outcome.session, source, outcome.sequence, 0)
                if journal["base"] == record["digest"]:
                    replayed = self._replay(outcome.session, journal["entries"],
                                            content, project, rules=rules)
                    require(replayed.recording()["digest"] == journal["head"],
                            "Long-session head mismatch")
                    return LongSessionStatus(replayed, source, outcome.sequence,
                                             len(journal["entries"]))
                if journal["head"] == record["digest"]:
                    # Crash AFTER publishing the compacted snapshot but BEFORE
                    # clearing the old journal. Never apply its actions twice.
                    return LongSessionStatus(outcome.session, source, outcome.sequence, 0)
                if source == "backup" and not journal["entries"]:
                    # The journal references the lost newer checkpoint. Expose
                    # an older recovery candidate without rewriting anything.
                    return LongSessionStatus(outcome.session, source, outcome.sequence,
                                             0, degraded=True)
                raise RuleError("Journal does not belong to this checkpoint")
            except (RuleError, OSError) as exc:
                if source == "primary" and verified_file:
                    # A valid primary with an incompatible journal must NOT
                    # silently fall back to an older valid backup. That could
                    # discard a committed action while reporting success.
                    raise
                errors.append(str(exc))
        raise RuleError("No recoverable long-session state: " + "; ".join(errors))

    def load(self, content, project, *, rules=None):
        return self.load_with_status(content, project, rules=rules).session

    def _current_journal(self, status):
        journal = self._read_journal()
        current_digest = status.session.recording()["digest"]
        if journal is None:
            return self._empty(current_digest)
        if journal["head"] == current_digest and journal["base"] != current_digest:
            # This may be an un-compacted journal OR a crash at the compact
            # boundary. Compare with primary's canonical checkpoint.
            _, primary = self.store._read(
                self.store.path, status.session.content, status.session.project,
                rules=status.session.rules)
            if primary.session.recording()["digest"] == current_digest:
                receipts = journal["receipts"] + [
                    e["request_id"] for e in journal["entries"]]
                return self._empty(current_digest, dict.fromkeys(receipts))
        return journal

    @exclusive_write
    def perform(self, session, request_id, operation, *args, **kwargs):
        """Execute once, durably journal, then opportunistically compact.

        A request_id is caller-supplied and stable across retries. Recent IDs
        remain deduplicated across checkpoint compaction (bounded receipts).
        Do not share a path between independent concurrent writers.
        """
        require(isinstance(session, GameSession), "Expected GameSession")
        require(self.journal.is_file(), "Initialize or explicitly migrate this long-session slot")
        require(isinstance(request_id, str) and 0 < len(request_id) <= 128,
                "Invalid operation request ID")
        require(operation in OPERATIONS, "Unsupported journaled operation")
        status = self.load_with_status(session.content, session.project,
                                       rules=session.rules)
        require(not status.degraded, "Restore the damaged save explicitly before writing")
        require(session.recording() == status.session.recording(),
                "In-memory session differs from durable journal")
        obj = self._current_journal(status)
        known = set(obj["receipts"]) | {step["request_id"] for step in obj["entries"]}
        if request_id in known:
            return JournalResult(False)
        if len(obj["entries"]) >= self.checkpoint_every:
            # A previous compact failed after the journal commit. Never append
            # beyond the verified bound or mutate before space is available.
            self._compact_verified(session, obj)
            obj = self._current_journal(self.load_with_status(
                session.content, session.project, rules=session.rules))
        require(obj["head"] == session.recording()["digest"], "Stale journal head")
        # Explicit JSON encoding prevents an unserializable operation from
        # changing state before its arguments can be persisted.
        try:
            arguments = json.loads(json.dumps([list(args), kwargs], ensure_ascii=False,
                                              allow_nan=False))
        except (ValueError, TypeError, RecursionError) as exc:
            raise RuleError(f"Operation arguments are not JSON-compatible: {exc}") from exc
        before_record = session.recording()
        before = obj["head"]
        value = getattr(session, operation)(*args, **kwargs)
        record = session.recording()
        GameSession.from_recording(record, session.content, session.project,
                                   rules=session.rules)
        step = {"request_id": request_id, "operation": operation,
                "args": arguments[0], "kwargs": arguments[1],
                "before": before, "after": record["digest"]}
        # Engine Battle IDs are generated on encounter entry. Rather than
        # assuming an equivalent random UUID on replay, record an additional
        # replay-validated boundary only when tactical identities changed.
        def identities(value):
            if value["mode"] == "battle":
                return ("battle", value["tactical"]["battle_id"])
            if value["mode"] == "fronts":
                return ("fronts", value.get("front_battle_ids"))
            return ("campaign", None)
        if identities(before_record) != identities(record):
            step["snapshot"] = record
        updated = {**obj, "entries": obj["entries"] + [step],
                   "head": record["digest"]}
        self._publish(updated)  # Durable commit point for accepted action.
        compacted = False
        if len(updated["entries"]) >= self.checkpoint_every:
            try:
                self._compact_verified(session, updated)
                compacted = True
            except (OSError, RuleError):
                # Action is already durable in the journal. Compaction can be
                # retried later; never make the caller re-apply the action.
                pass
        return JournalResult(True, value, compacted)

    def _compact_verified(self, session, journal):
        record = session.recording()
        require(journal["head"] == record["digest"], "Cannot compact a divergent replay")
        GameSession.from_recording(record, session.content, session.project,
                                   rules=session.rules)
        self.store.save(session)
        receipts = list(dict.fromkeys(
            journal["receipts"] + [e["request_id"] for e in journal["entries"]]))
        # If this fails, the old journal head matches the new snapshot; load
        # will recognize the stale journal, without duplicating any operation.
        self._publish(self._empty(record["digest"], receipts))

    @exclusive_write
    def compact(self, content, project, *, rules=None):
        status = self.load_with_status(content, project, rules=rules)
        require(not status.degraded, "Recover the damaged checkpoint before compacting")
        journal = self._current_journal(status)
        if journal["entries"]:
            self._compact_verified(status.session, journal)
        return status.session

    def migrate_from(self, old_path, content, project, *, rules=None):
        """Explicit, non-destructive v1/v2 -> new long-session destination."""
        old = Path(old_path)
        require(old.resolve() != self.store.path.resolve(),
                "Choose a distinct destination; source must be retained")
        outcome = SessionStore(old).load_with_status(content, project, rules=rules)
        self.initialize(outcome.session)
        require(self.load(content, project, rules=rules).recording() ==
                outcome.session.recording(), "Migration verification failed")
        return outcome

    @exclusive_write
    def restore(self, status, *, expected_digest):
        """Explicit restoration; preserve the damaged primary as .damaged.

        The caller must show status.source/degraded to the user and provide
        the exact expected recording digest as an acknowledgement.
        """
        require(isinstance(status, LongSessionStatus) and
                status.session.recording()["digest"] == expected_digest,
                "Recovery acknowledgement mismatch")
        # The UI's recovery preview may be stale. Re-read both candidates
        # under the exclusive writer lock before replacing any bytes.
        latest = self.load_with_status(status.session.content, status.session.project,
                                       rules=status.session.rules)
        require(latest.source == status.source and
                latest.sequence == status.sequence and
                latest.degraded == status.degraded and
                latest.session.recording()["digest"] == expected_digest,
                "Recovery selection is stale; inspect the slot again")
        require(status.source == "backup" or status.degraded,
                "No damaged checkpoint to restore")
        damaged = self.store.path.with_name(self.store.path.name + ".damaged")
        require(not damaged.exists(), "Damaged evidence already exists")
        if self.store.path.exists():
            write_bytes(damaged, self.store.path.read_bytes())
        self.store.save(status.session)
        journal = self._read_journal()
        receipts = ([] if journal is None else
                    journal["receipts"] + [e["request_id"] for e in journal["entries"]])
        self._publish(self._empty(expected_digest, dict.fromkeys(receipts)))
        return self.load_with_status(status.session.content, status.session.project,
                                     rules=status.session.rules)


class LongSessionAutosave:
    """Controller facade with rollback when an operation was not persisted."""

    def __init__(self, session, store):
        self.session, self.store = session, store

    def perform(self, request_id, operation, *args, **kwargs):
        before = self.session.recording()
        try:
            return self.store.perform(self.session, request_id, operation, *args, **kwargs)
        except Exception:
            # If the journal write failed, the disk still contains the old
            # state. If it succeeded, recover exactly the persisted new state.
            self.session = self.store.load(
                self.session.content, self.session.project, rules=self.session.rules)
            raise
