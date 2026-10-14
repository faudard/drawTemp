"""R8.19 — Read-only save catalogue, checkpoint diff and guided restore.

Headless model for the Player. Existing SessionStore v2, LongSessionStore and
LongSessionMaintenance remain the only persistence formats and validators.
Restoration deliberately targets an unused DIFFERENT long-session slot.
"""
from __future__ import annotations

from pathlib import Path

from .game_session import digest
from .long_session import LongSessionStore
from .model import RuleError, require
from .persistence import SessionStore
from .save_maintenance import LongSessionMaintenance
from .session_lock import session_writer_lock

_SUMMARY_FIELDS = ("completed", "unlocked", "gold", "experience", "flags",
                   "reputation", "resources", "companions", "party", "inventory",
                   "story_history", "choices", "missions", "consequences")
_DIFF_LIMIT = 24


def _as_list(value):
    if isinstance(value, dict):
        return sorted(str(k) for k in value)
    if isinstance(value, (list, tuple, set)):
        return sorted(str(k) for k in value)
    return []


def snapshot_summary(record):
    """Concise, non-mutating display projection from a verified recording."""
    progress = record.get("progress") or {}
    summary = {"campaign": record["campaign_id"], "mode": record["mode"],
               "digest": record["digest"], "seed": record["seed"],
               "finalized": bool(record.get("finalized")),
               "completed": _as_list(progress.get("completed", [])),
               "unlocked": _as_list(progress.get("unlocked", []))}
    for name in _SUMMARY_FIELDS:
        if name in ("completed", "unlocked") or name not in progress:
            continue
        value = progress[name]
        if isinstance(value, (str, int, float, bool)) or value is None:
            summary[name] = value
        elif isinstance(value, (list, dict)):
            summary[name] = len(value)
    tactical = record.get("tactical")
    if isinstance(tactical, dict):
        summary["tactical_entries"] = len(tactical.get("commands", []))
    return summary


def compare_recordings(left, right):
    """Compare gameplay without interpreting campaign internals or mutating it."""
    require(left["campaign_id"] == right["campaign_id"],
            "Cannot compare saves from different campaigns")
    a, b = snapshot_summary(left), snapshot_summary(right)
    differences = []
    for key in sorted(set(a) | set(b)):
        if key == "digest":
            continue
        if a.get(key) != b.get(key):
            differences.append({"field": key, "current": a.get(key),
                                "selected": b.get(key)})
    # Flag/config changes can be important even if container lengths match.
    before, after = left.get("progress", {}), right.get("progress", {})
    for key in sorted(set(before) | set(after)):
        if key in ("completed", "unlocked"):
            continue
        if before.get(key) == after.get(key):
            continue
        if any(d["field"] == key for d in differences):
            continue
        differences.append({"field": key, "current": "modified",
                            "selected": "modified"})
    return {"same": left["digest"] == right["digest"],
            "current": a, "selected": b,
            "fields": differences[:_DIFF_LIMIT],
            "truncated": len(differences) > _DIFF_LIMIT,
            "warning": ("A previous generation may omit missions, rewards, "
                        "choices and multi-front state added later.")}


class SaveManagerModel:
    """No Tk. Validates named save slots and archived recordings on demand."""

    def __init__(self, player):
        self.player = player

    def _path(self, campaign_id, slot, kind):
        require(kind in ("long", "v2"), "Unsupported save slot type")
        return (self.player.long_path_for(campaign_id, slot) if kind == "long"
                else self.player.path_for(campaign_id, slot))

    def _maintenance(self, campaign_id, slot):
        return LongSessionMaintenance(
            self._path(campaign_id, slot, "long"),
            self.player.content, self.player.project, rules=self.player.rules)

    def _long_state(self, campaign_id, slot):
        manager = self._maintenance(campaign_id, slot)
        inventory = manager.inspect()
        inventory["campaign_id"] = campaign_id
        inventory["slot"] = slot
        inventory["kind"] = "long"
        return inventory

    def _v2_state(self, campaign_id, slot):
        path = self._path(campaign_id, slot, "v2")
        store = SessionStore(path)
        if not path.exists() and not store.backup.exists():
            return {"campaign_id": campaign_id, "slot": slot, "kind": "v2",
                    "status": "missing", "issues": [], "archives": []}
        try:
            outcome = store.load_with_status(
                self.player.content, self.player.project, rules=self.player.rules)
            require(outcome.session.campaign_id == campaign_id,
                    "Save campaign identity does not match selected slot")
            return {"campaign_id": campaign_id, "slot": slot, "kind": "v2",
                    "status": "healthy" if outcome.source == "primary" else "degraded",
                    "source": outcome.source, "sequence": outcome.sequence,
                    "session_digest": outcome.session.recording()["digest"],
                    "issues": [], "archives": []}
        except (RuleError, OSError) as exc:
            return {"campaign_id": campaign_id, "slot": slot, "kind": "v2",
                    "status": "invalid", "issues": [str(exc)], "archives": []}

    def list_slots(self, campaign_id):
        require(self.player.project.campaign(campaign_id) is not None,
                "Unknown campaign")
        rows = []
        for slot in range(1, self.player.project.save_slots + 1):
            for kind in ("long", "v2"):
                row = (self._long_state(campaign_id, slot) if kind == "long"
                       else self._v2_state(campaign_id, slot))
                rows.append(row)
        return rows

    def inspect_slot(self, campaign_id, slot, kind):
        # path_for validates the slot index and campaign identity.
        self._path(campaign_id, slot, kind)
        return (self._long_state(campaign_id, slot) if kind == "long"
                else self._v2_state(campaign_id, slot))

    def _session_record(self, campaign_id, slot, kind):
        if kind == "long":
            status = LongSessionStore(self._path(campaign_id, slot, kind)).load_with_status(
                self.player.content, self.player.project, rules=self.player.rules)
        else:
            status = SessionStore(self._path(campaign_id, slot, kind)).load_with_status(
                self.player.content, self.player.project, rules=self.player.rules)
        require(status.session.campaign_id == campaign_id,
                "Slot belongs to a different campaign")
        return status.session.recording()

    def _archive_record(self, campaign_id, slot, generation):
        require(isinstance(generation, str) and generation,
                "Select a named, verified archived generation")
        manager = self._maintenance(campaign_id, slot)
        # Never concatenate an unchecked user-provided directory name into
        # a path that can be read, deleted or used for recovery.
        archives = manager._archive_dirs()
        archive = next((p for p in archives if p.name == generation), None)
        require(archive is not None, "Unknown archived generation")
        evidence = manager.verify_archive(archive)
        stored = LongSessionStore(
            archive / manager.path.name,
            checkpoint_every=manager.store.checkpoint_every)
        status = stored.load_with_status(
            self.player.content, self.player.project, rules=self.player.rules)
        require(status.source == "primary" and not status.degraded and
                status.session.campaign_id == campaign_id and
                status.session.recording()["digest"] == evidence["session_digest"],
                "Archive does not match the requested campaign")
        return evidence, status.session.recording()

    def history(self, campaign_id, slot, kind="long"):
        selected = self.inspect_slot(campaign_id, slot, kind)
        versions = []
        if selected["status"] in ("healthy", "degraded", "warning"):
            try:
                current = self._session_record(campaign_id, slot, kind)
                versions.append({"id": "current", "name": "Sauvegarde actuelle",
                                 "digest": current["digest"], "type": "current",
                                 "summary": snapshot_summary(current), "verified": True})
            except (RuleError, OSError):
                pass
        if kind == "long":
            for archive in selected.get("archives", []):
                version = {"id": archive["name"], "name": archive["name"],
                           "type": "archive", "verified": archive["verified"]}
                if archive["verified"]:
                    try:
                        _, rec = self._archive_record(campaign_id, slot, archive["name"])
                        version["digest"] = rec["digest"]
                        version["summary"] = snapshot_summary(rec)
                    except (RuleError, OSError) as exc:
                        version["verified"] = False
                        version["reason"] = str(exc)
                else:
                    version["reason"] = archive.get("reason", "Invalid archive")
                versions.append(version)
        return versions

    def compare_archive(self, campaign_id, slot, generation):
        _, historical = self._archive_record(campaign_id, slot, generation)
        try:
            current = self._session_record(campaign_id, slot, "long")
        except (RuleError, OSError):
            # If the current slot is corrupted, show archive details without
            # suggesting a comparison with an unverified state.
            return {"same": False, "current": None,
                    "selected": snapshot_summary(historical), "fields": [],
                    "truncated": False,
                    "warning": "La sauvegarde actuelle est illisible ou incompatible."}
        return compare_recordings(current, historical)

    def _destination_free(self, campaign_id, destination_slot):
        target = self._path(campaign_id, destination_slot, "long")
        evidence = [target, target.with_name(target.name + ".bak"),
                    target.with_name(target.name + ".journal"),
                    target.with_name(target.name + ".damaged"),
                    target.with_name(target.name + ".lock"),
                    target.with_name(target.name + ".history")]
        require(not any(p.exists() or p.is_symlink() for p in evidence),
                "Destination contains a save or recovery evidence; choose an empty slot")
        return target

    def restoration_plan(self, campaign_id, source_slot, generation,
                         destination_slot):
        require(source_slot != destination_slot,
                "Restore to a different free long-session slot")
        target = self._destination_free(campaign_id, destination_slot)
        evidence, record = self._archive_record(campaign_id, source_slot, generation)
        preview = self.compare_archive(campaign_id, source_slot, generation)
        token = digest({"kind": "save_manager_restore_r819",
                        "campaign": campaign_id, "source_slot": source_slot,
                        "destination_slot": destination_slot, "generation": generation,
                        "manifest": evidence["digest"], "session": record["digest"]})
        return {"campaign_id": campaign_id, "source_slot": source_slot,
                "destination_slot": destination_slot,
                "generation": generation, "destination": str(target),
                "digest": record["digest"], "summary": snapshot_summary(record),
                "comparison": preview, "token": token,
                "warning": ("Une COPIE sera créée dans un emplacement libre. "
                            "Ni la sauvegarde actuelle ni l'archive d'origine "
                            "ne seront remplacées.")}

    def restore_to_free_slot(self, campaign_id, source_slot, generation,
                             destination_slot, *, expected_token):
        """Explicit confirmation, revalidation and no overwrite of any source."""
        require(isinstance(expected_token, str) and len(expected_token) == 64,
                "Confirm the exact restoration preview first")
        source = self._path(campaign_id, source_slot, "long")
        with session_writer_lock(source):
            preview = self.restoration_plan(
                campaign_id, source_slot, generation, destination_slot)
            require(preview["token"] == expected_token,
                    "Restoration preview changed; inspect and confirm again")
            _, record = self._archive_record(campaign_id, source_slot, generation)
            target = self._destination_free(campaign_id, destination_slot)
            archive = LongSessionStore(target)
            from .game_session import GameSession
            session = GameSession.from_recording(
                record, self.player.content, self.player.project,
                rules=self.player.rules)
            archive.initialize(session)
            require(archive.load(self.player.content, self.player.project,
                                 rules=self.player.rules).recording() == record,
                    "Restored session failed replay verification")
            return {"campaign_id": campaign_id, "slot": destination_slot,
                    "kind": "long", "digest": record["digest"],
                    "source_generation": generation, "verified": True}
