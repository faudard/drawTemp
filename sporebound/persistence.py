"""Persistence 2.0: versioned, replay-verified checkpoints and crash recovery.

Opt-in adapter for GameSession; it never rewrites legacy campaign slot files.
A successful write retains the previous verified generation as a backup.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re

from .game_session import GameSession, digest
from .model import RuleError, require
from .storage import json_text, write_json

_CHECKSUM = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class RecoveryResult:
    session: GameSession
    source: str
    sequence: int
    migrated_from_v1: bool


class SessionStore:
    """One active checkpoint and one verified recovery generation.

    Files: <path> and <path>.bak. No automatic repair or silent data overwrite.
    Caller-provided content/project/rules must match the saved identities.
    """

    VERSION = 2

    def __init__(self, path, *, max_bytes=64 * 1024 * 1024):
        require(type(max_bytes) is int and 0 < max_bytes <= 512 * 1024 * 1024,
                "Invalid checkpoint size limit")
        self.path = Path(path)
        self.backup = self.path.with_name(self.path.name + ".bak")
        self.max_bytes = max_bytes

    def _decode(self, obj, content, project, *, rules=None):
        require(isinstance(obj, dict), "Invalid checkpoint document")
        if obj.get("kind") == "game_session" and obj.get("version") == 1:
            return RecoveryResult(
                GameSession.from_recording(obj, content, project, rules=rules),
                "", 0, True)
        require(obj.get("kind") == "session_checkpoint" and
                type(obj.get("version")) is int and obj["version"] == self.VERSION,
                "Unsupported checkpoint version")
        require(set(obj) == {"kind", "version", "sequence", "previous",
                             "session", "digest"}, "Malformed checkpoint")
        require(type(obj["sequence"]) is int and obj["sequence"] >= 1,
                "Invalid checkpoint sequence")
        previous = obj["previous"]
        require(previous is None or
                (isinstance(previous, str) and _CHECKSUM.fullmatch(previous)),
                "Invalid previous checkpoint checksum")
        require(isinstance(obj["digest"], str) and
                _CHECKSUM.fullmatch(obj["digest"]), "Invalid checkpoint checksum")
        body = {key: value for key, value in obj.items() if key != "digest"}
        require(digest(body) == obj["digest"], "Checkpoint checksum mismatch")
        session = GameSession.from_recording(obj["session"], content, project, rules=rules)
        return RecoveryResult(session, "", obj["sequence"], False)

    def _read(self, path, content, project, *, rules=None):
        require(path.stat().st_size <= self.max_bytes, "Checkpoint exceeds size limit")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result = self._decode(data, content, project, rules=rules)
        except (OSError, UnicodeError, ValueError, TypeError, KeyError,
                AttributeError, RecursionError) as exc:
            raise RuleError(f"Invalid checkpoint {path.name}: {exc}") from exc
        return data, result

    def load_with_status(self, content, project, *, rules=None):
        """Prefer primary, recover the verified previous generation if needed."""
        errors = []
        for path in (self.path, self.backup):
            if not path.exists():
                errors.append(f"{path.name}: missing")
                continue
            try:
                _, outcome = self._read(path, content, project, rules=rules)
                return RecoveryResult(outcome.session,
                                      "primary" if path == self.path else "backup",
                                      outcome.sequence, outcome.migrated_from_v1)
            except (RuleError, OSError) as exc:
                errors.append(str(exc))
        raise RuleError("No valid session checkpoint: " + "; ".join(errors))

    def load(self, content, project, *, rules=None):
        return self.load_with_status(content, project, rules=rules).session

    def save(self, session: GameSession):
        """Preflight, retain last good checkpoint, then atomically publish v2.

        A corrupt primary is never promoted to backup. If both generations are
        invalid, refuse to overwrite evidence of a damaged session.
        """
        require(isinstance(session, GameSession), "Expected GameSession")
        record = session.recording()  # Verifies tactical replay before disk writes.
        GameSession.from_recording(record, session.content, session.project,
                                   rules=session.rules)
        old_data, old_status = None, None
        exists = self.path.exists() or self.backup.exists()
        if exists:
            for path in (self.path, self.backup):
                if not path.exists():
                    continue
                try:
                    candidate, result = self._read(
                        path, session.content, session.project, rules=session.rules)
                except (RuleError, OSError):
                    continue
                require(result.session.campaign_id == session.campaign_id,
                        "Cannot overwrite a different campaign")
                old_data, old_status = candidate, result
                break
            require(old_data is not None, "No valid prior checkpoint: refusing overwrite")

        sequence = (old_status.sequence if old_status else 0) + 1
        checkpoint = {"kind": "session_checkpoint", "version": self.VERSION,
                      "sequence": sequence,
                      "previous": old_data.get("digest") if old_data else None,
                      "session": record}
        checkpoint["digest"] = digest(checkpoint)
        require(len(json_text(checkpoint).encode("utf-8"))
                <= self.max_bytes, "Checkpoint exceeds size limit")
        if old_data is not None:
            # Do not erase the sole good backup when the primary is corrupt.
            if self.path.exists():
                try:
                    self._read(self.path, session.content, session.project,
                               rules=session.rules)
                except (RuleError, OSError):
                    pass
                else:
                    write_json(self.backup, old_data)
        write_json(self.path, checkpoint)
        return self.path

    @staticmethod
    def import_player_slot(project_path, project, content, campaign_id, slot,
                           *, seed=1, rules=None):
        """Read a v1 campaign slot into a new session; never edit its original."""
        from .game_project import load_slot
        progress = load_slot(project_path, project, content, campaign_id, slot)
        session = GameSession.new(content, project, campaign_id,
                                  seed=seed, rules=rules)
        session.progress = progress
        return session


class AutosaveSession:
    """Opt-in, synchronous saves only after an accepted gameplay operation."""

    OPERATIONS = frozenset({
        "choose_story_option", "start_mission", "start_fronts", "execute",
        "switch_front", "advance_fronts", "set_doctrine", "ai_turn",
        "return_to_campaign", "abandon_encounter",
    })

    def __init__(self, session: GameSession, store: SessionStore):
        self.session = session
        self.store = store

    def perform(self, operation, *args, **kwargs):
        require(operation in self.OPERATIONS, "Unsupported autosave operation")
        result = getattr(self.session, operation)(*args, **kwargs)
        # If the disk write fails the in-memory gameplay change remains valid;
        # the last successful checkpoint is preserved for recovery.
        self.store.save(self.session)
        return result
