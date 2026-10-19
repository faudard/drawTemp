"""R1.8: verified, atomic Player v1 slots with explicit backup recovery.

Keeps existing slot_N.json and slot_N.json.bak paths and GameSession v1
records, so R12 and legacy user data remain compatible. SessionStore v2
and LongSessionStore remain the opt-in advanced journal implementations.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from drawtemp.core import RuleError
from drawtemp.sdk.simulation import Simulation
from sporebound.session_lock import session_writer_lock
from sporebound.storage import write_bytes


class SlotError(RuleError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class SlotInspection:
    primary: str
    backup: str
    recoverable: bool
    message: str = ""


class PlayerSlotStore:
    """One canonical save path. Never silently selects a backup."""

    def __init__(self, path, content, project, *, campaign_id):
        self.path = Path(path)
        self.backup = self.path.with_suffix(".json.bak")
        self.damaged = self.path.with_suffix(".json.damaged")
        self.content = content
        self.project = project
        self.campaign_id = campaign_id
        if self.path.suffix != ".json" or self.path.name.endswith(".game.json"):
            raise SlotError("invalid_path", "Expected a Player slot .json file")

    def _safe(self, path):
        if path.is_symlink():
            raise SlotError("unsafe_path", "Refusing symlink in Player slot: " + path.name)

    def _load(self, path):
        self._safe(path)
        loaded = Simulation.load(path, self.content, self.project)
        if loaded.recording()["campaign_id"] != self.campaign_id:
            raise SlotError("wrong_campaign", "Save belongs to another campaign")
        return loaded

    def inspect(self):
        """Read-only; corruption and compatibility errors are never repaired."""
        status = {}
        errors = []
        for role, path in (("primary", self.path), ("backup", self.backup)):
            if not path.exists() and not path.is_symlink():
                status[role] = "missing"
                continue
            try:
                self._load(path)
                status[role] = "valid"
            except (RuleError, OSError, ValueError) as exc:
                status[role] = "invalid"
                errors.append(role + ": " + str(exc))
        return SlotInspection(status["primary"], status["backup"],
                              status["backup"] == "valid", "; ".join(errors))

    def load(self):
        """Primary only: caller explicitly decides whether to restore backup."""
        return self._load(self.path)

    def save(self, session: Simulation):
        if not isinstance(session, Simulation):
            raise SlotError("invalid_session", "Expected an R1 Simulation handle")
        if session.recording()["campaign_id"] != self.campaign_id:
            raise SlotError("wrong_campaign", "Cannot save another campaign")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with session_writer_lock(self.path):
            # Validate filesystem targets *after* acquiring the writer lock:
            # the slot may have been swapped while waiting to enter.
            self._safe(self.path)
            self._safe(self.backup)
            self._safe(self.damaged)
            if self.path.exists():
                # Never promote a corrupt primary to the only good backup.
                self._load(self.path)
                if self.backup.exists():
                    self._load(self.backup)
                current_bytes = self.path.read_bytes()
            else:
                current_bytes = None
                if self.backup.exists():
                    raise SlotError("recovery_required", "Orphan backup: restore explicitly")
            # Reject invalid engine state *before* overwriting any generation.
            record = session.recording()
            from drawtemp.sdk.replay import verify_recording
            verify_recording(record, self.content, self.project)
            if current_bytes is not None:
                write_bytes(self.backup, current_bytes)
            session.save(self.path)  # canonical atomic replace
            loaded = self._load(self.path)
            if loaded.recording() != record:
                raise SlotError("verification_failed", "Saved checkpoint differs from live game")
        return self.path

    def restore_backup(self):
        """Explicit user action, preserving corrupt primary bytes as evidence."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with session_writer_lock(self.path):
            self._safe(self.path)
            self._safe(self.backup)
            self._safe(self.damaged)
            if not self.backup.is_file():
                raise SlotError("backup_missing", "No backup to restore")
            loaded = self._load(self.backup)
            raw = self.backup.read_bytes()
            if self.path.exists():
                try:
                    self._load(self.path)
                except (RuleError, OSError, ValueError):
                    # A previous restore may have crashed after archiving the
                    # bad primary but before publishing the verified backup.
                    # Re-use ONLY identical evidence; different corruption
                    # must not overwrite the existing forensic copy.
                    damaged_bytes = self.path.read_bytes()
                    if self.damaged.exists():
                        if self.damaged.read_bytes() != damaged_bytes:
                            raise SlotError("evidence_exists",
                                            "A different damaged copy already exists")
                    else:
                        write_bytes(self.damaged, damaged_bytes)
                else:
                    # Manual-slot callers (not only autosave UI) must never
                    # silently downgrade a still-valid checkpoint.
                    raise SlotError("primary_valid",
                                    "Refusing to replace a valid primary with an older backup")
            write_bytes(self.path, raw)
            verified = self._load(self.path)
            if verified.recording() != loaded.recording():
                raise SlotError("verification_failed", "Restored checkpoint does not match backup")
            return verified
