"""R8.18: fail-closed, opt-in maintenance for verified long-session slots.

The live primary, backup, journal, and .damaged recovery evidence are never
pruned or rewritten here. Archiving, retention and temp quarantine share the
same per-slot single-writer lease used by LongSessionStore.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile
import time

from .game_session import digest
from .long_session import LongSessionStore
from .model import RuleError, require
from .session_lock import session_writer_lock
from .storage import write_json

_ARCHIVE_NAME = re.compile(r"^gen-[0-9]{20}-[0-9a-f]{12}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_MAX_ARCHIVES = 1000
_MAX_TEMP_CANDIDATES = 128
_MAX_BYTES = 64 * 1024 * 1024


def _sha(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for data in iter(lambda: source.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def _regular(path):
    """Never follow symbolic links, including at the top-level file."""
    return path.is_file() and not path.is_symlink()


class LongSessionMaintenance:
    """Inspect, archive, and manually retire copies of an existing long slot.

    Every mutating operation is an explicit user action and excludes all
    cooperative session writers. There is intentionally no automatic purge.
    """

    VERSION = 1

    def __init__(self, path, content, project, *, rules=None, checkpoint_every=32):
        self.path = Path(path)
        self.content, self.project, self.rules = content, project, rules
        self.store = LongSessionStore(path, checkpoint_every=checkpoint_every)
        self.history = self.path.with_name(self.path.name + ".history")
        self.quarantine = self.history / "quarantine"

    def _ensure_history(self):
        require(not self.history.is_symlink() and
                (not self.history.exists() or self.history.is_dir()),
                "Unsafe archive history directory")
        self.history.mkdir(parents=True, exist_ok=True)

    def _live(self):
        return (("primary", self.path),
                ("backup", self.store.store.backup),
                ("journal", self.store.journal),
                ("damaged", self.path.with_name(self.path.name + ".damaged")),
                ("writer_lock", self.path.with_name(self.path.name + ".lock")))

    def _temps(self):
        if not self.path.parent.exists():
            return []
        names = (self.path.name + ".", self.path.name + ".bak.",
                 self.path.name + ".journal.")
        candidates = []
        for p in self.path.parent.iterdir():
            if (p.name.endswith(".tmp") and
                    any(p.name.startswith(prefix) for prefix in names)):
                candidates.append(p)
        require(len(candidates) <= _MAX_TEMP_CANDIDATES,
                "Too many orphan temporaries; investigate manually")
        return sorted(candidates, key=lambda p: p.name)

    def inspect(self):
        """Read-only diagnostic: no repair, deletion or lock acquisition."""
        items, issues = [], []
        for name, path in self._live():
            if not path.exists() and not path.is_symlink():
                continue
            entry = {"role": name, "name": path.name,
                     "bytes": 0, "status": "evidence"}
            if not _regular(path):
                entry["status"] = "unsafe"
                issues.append(f"{name}: not a regular file")
            else:
                entry["bytes"] = path.stat().st_size
                if name in ("primary", "backup", "journal"):
                    try:
                        limit = (self.store.max_journal_bytes if name == "journal"
                                 else self.store.store.max_bytes)
                        require(entry["bytes"] <= limit, f"{name}: too large")
                        if name == "journal":
                            self.store._read_journal()
                        else:
                            self.store.store._read(path, self.content, self.project,
                                                    rules=self.rules)
                        entry["sha256"] = _sha(path)
                        entry["status"] = "verified"
                    except (RuleError, OSError, ValueError) as exc:
                        entry["status"] = "invalid"
                        issues.append(f"{name}: {exc}")
            items.append(entry)
        temps = []
        for p in self._temps():
            temps.append({"name": p.name, "bytes": p.stat().st_size if _regular(p) else 0,
                          "status": "orphan_candidate" if _regular(p) else "unsafe"})
        status = "missing"
        source, game_digest, sequence, replayed = None, None, None, None
        if self.path.exists() or self.store.store.backup.exists():
            try:
                require(self.store.journal.is_file() and
                        not self.store.journal.is_symlink(),
                        "Long-session journal is missing or unsafe")
                verified = self.store.load_with_status(
                    self.content, self.project, rules=self.rules)
                source, sequence, replayed = (
                    verified.source, verified.sequence, verified.applied)
                game_digest = verified.session.recording()["digest"]
                status = ("healthy" if source == "primary" and not verified.degraded
                          else "degraded")
            except (RuleError, OSError) as exc:
                status = "invalid"
                issues.append(f"replay: {exc}")
        if any(item["status"] in ("unsafe", "invalid") for item in items):
            if status == "healthy":
                status = "warning"
        if any(item["role"] == "writer_lock" for item in items):
            issues.append("writer lock present; no automatic stale-lock takeover")
        if temps:
            issues.append("temporary files present; manual quarantine only")
        archived = []
        try:
            for path in self._archive_dirs():
                try:
                    archived.append(self.verify_archive(path))
                except (RuleError, OSError, ValueError) as exc:
                    archived.append({"name": path.name, "verified": False,
                                     "reason": str(exc)})
                    issues.append(f"archive {path.name}: {exc}")
        except (RuleError, OSError) as exc:
            issues.append(f"archive inventory: {exc}")
        return {"format": "long_session_maintenance", "version": self.VERSION,
                "slot": str(self.path), "status": status, "source": source,
                "sequence": sequence, "replayed": replayed,
                "session_digest": game_digest, "assets": items,
                "temporary": temps, "archives": archived, "issues": issues}

    def _archive_dirs(self):
        if not self.history.exists():
            return []
        require(self.history.is_dir() and not self.history.is_symlink(),
                "Unsafe archive history directory")
        archives = []
        for p in self.history.iterdir():
            if _ARCHIVE_NAME.fullmatch(p.name):
                require(p.is_dir() and not p.is_symlink(),
                        f"Unsafe archive generation: {p.name}")
                archives.append(p)
        require(len(archives) <= _MAX_ARCHIVES,
                "Too many archives; manual intervention required")
        return sorted(archives, key=lambda p: p.name, reverse=True)

    def _manifest(self, archive):
        require(archive.parent == self.history and
                _ARCHIVE_NAME.fullmatch(archive.name) and
                archive.is_dir() and not archive.is_symlink(),
                "Invalid archive location")
        manifest_path = archive / "manifest.json"
        require(_regular(manifest_path) and manifest_path.stat().st_size < 65536,
                "Invalid archive manifest")
        import json
        try:
            obj = json.loads(manifest_path.read_text(encoding="utf-8"))
            require(isinstance(obj, dict) and
                    set(obj) == {"kind", "version", "sequence",
                                 "session_digest", "files", "digest"} and
                    obj["kind"] == "long_session_archive" and
                    type(obj["version"]) is int and obj["version"] == self.VERSION and
                    type(obj["sequence"]) is int and obj["sequence"] >= 1 and
                    isinstance(obj["session_digest"], str) and
                    _HASH.fullmatch(obj["session_digest"]) and
                    isinstance(obj["digest"], str) and _HASH.fullmatch(obj["digest"]) and
                    digest({k: v for k, v in obj.items() if k != "digest"}) ==
                    obj["digest"], "Archive manifest mismatch")
            files = obj["files"]
            require(isinstance(files, list) and 2 <= len(files) <= 3,
                    "Invalid archive file manifest")
            allowed = {self.path.name, self.path.name + ".bak",
                       self.path.name + ".journal"}
            names = [item["name"] for item in files]
            require(set(names).issubset(allowed) and
                    {self.path.name, self.path.name + ".journal"}.issubset(names) and
                    len(set(names)) == len(names), "Unexpected archive file names")
            require({p.name for p in archive.iterdir()} ==
                    set(names) | {"manifest.json"},
                    "Unrecognized archive files; refusing maintenance")
            for item in files:
                require(isinstance(item, dict) and
                        set(item) == {"name", "size", "sha256"} and
                        type(item["size"]) is int and 0 <= item["size"] <= _MAX_BYTES and
                        isinstance(item["sha256"], str) and
                        _HASH.fullmatch(item["sha256"]), "Invalid archive metadata")
                path = archive / item["name"]
                require(_regular(path) and
                        path.stat().st_size == item["size"] and
                        _sha(path) == item["sha256"],
                        f"Archive file corrupted: {item['name']}")
        except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
            raise RuleError(f"Invalid archive: {exc}") from exc
        return obj

    def verify_archive(self, archive):
        """Check byte-level manifest and replay from a separate archive path."""
        archive = Path(archive)
        obj = self._manifest(archive)
        store = LongSessionStore(archive / self.path.name,
                                 checkpoint_every=self.store.checkpoint_every)
        status = store.load_with_status(self.content, self.project, rules=self.rules)
        require(status.source == "primary" and not status.degraded and
                status.session.recording()["digest"] == obj["session_digest"] and
                status.sequence == obj["sequence"],
                "Archived session replay differs from its manifest")
        return {"name": archive.name, "digest": obj["digest"],
                "session_digest": obj["session_digest"],
                "sequence": obj["sequence"], "verified": True}

    def archive_verified(self):
        """Copy a consistent live generation; publish directory atomically."""
        with session_writer_lock(self.path):
            inventory = self.inspect()
            require(inventory["status"] == "healthy" and
                    all(item["status"] == "verified" for item in inventory["assets"]
                        if item["role"] in ("primary", "backup", "journal")),
                    "Refusing to archive unverified or degraded live state")
            self._ensure_history()
            name = (f"gen-{time.time_ns():020d}-"
                    f"{inventory['session_digest'][:12]}")
            target = self.history / name
            require(not target.exists(), "Archive name collision")
            stage = Path(tempfile.mkdtemp(prefix=".staging-", dir=self.history))
            try:
                assets = []
                for role, source in self._live():
                    if role not in ("primary", "backup", "journal") or not source.exists():
                        continue
                    require(_regular(source), "Unsafe live source file")
                    destination = stage / source.name
                    with source.open("rb") as reader, destination.open("xb") as writer:
                        shutil.copyfileobj(reader, writer, 1024 * 1024)
                        writer.flush()
                        os.fsync(writer.fileno())
                    assets.append({"name": source.name, "size": destination.stat().st_size,
                                   "sha256": _sha(destination)})
                obj = {"kind": "long_session_archive", "version": self.VERSION,
                       "sequence": inventory["sequence"],
                       "session_digest": inventory["session_digest"],
                       "files": assets}
                obj["digest"] = digest(obj)
                write_json(stage / "manifest.json", obj)
                # Verify as though already published, without altering any
                # primary/journal/backup. The commit is one directory rename.
                os.replace(stage, target)
                verified = self.verify_archive(target)
                return verified
            finally:
                if stage.exists():
                    shutil.rmtree(stage)

    def retention_plan(self, *, keep=3):
        require(type(keep) is int and 2 <= keep <= 100,
                "Keep at least two verified archive generations")
        archives = self._archive_dirs()
        verified = [self.verify_archive(p) for p in archives]
        candidates = verified[keep:]
        summary = {"keep": keep, "generations": [
            {"name": v["name"], "digest": v["digest"]} for v in verified]}
        return {"keep": keep, "preserve": [x["name"] for x in verified[:keep]],
                "remove": [x["name"] for x in candidates],
                "token": digest(summary)}

    def prune_archives(self, *, keep=3, expected_token):
        """Irreversible removal of ONLY old, independently verified COPIES.

        Caller must have displayed a dry-run retention plan and supplied the
        exact token; a changed archive inventory invalidates the plan.
        """
        require(isinstance(expected_token, str) and _HASH.fullmatch(expected_token),
                "Explicit retention plan token required")
        with session_writer_lock(self.path):
            inventory = self.inspect()
            require(inventory["status"] == "healthy",
                    "Do not prune archives when the active slot is degraded")
            current = self.retention_plan(keep=keep)
            require(current["token"] == expected_token,
                    "Retention plan is stale; inspect and confirm it again")
            for name in current["remove"]:
                archive = self.history / name
                self.verify_archive(archive)
                shutil.rmtree(archive)
            return current

    def temp_plan(self, *, min_age_seconds=3600):
        require(type(min_age_seconds) in (int, float) and
                60 <= min_age_seconds <= 365 * 86400,
                "Temporary age must be at least one minute")
        now = time.time()
        selected = []
        for path in self._temps():
            if not _regular(path):
                continue
            stat = path.stat()
            if (now - stat.st_mtime >= min_age_seconds and
                    stat.st_size <= _MAX_BYTES):
                selected.append({"name": path.name, "size": stat.st_size,
                                 "sha256": _sha(path), "mtime_ns": stat.st_mtime_ns})
        return {"count": len(selected), "files": selected,
                "token": digest({"min_age_seconds": min_age_seconds,
                                 "files": selected})}

    def quarantine_temps(self, *, min_age_seconds=3600, expected_token):
        """Explicitly MOVE orphan candidates aside; never delete temp bytes."""
        require(isinstance(expected_token, str) and _HASH.fullmatch(expected_token),
                "Explicit cleanup plan token required")
        with session_writer_lock(self.path):
            inventory = self.inspect()
            require(inventory["status"] == "healthy",
                    "Inspect and recover the active slot before moving evidence")
            current = self.temp_plan(min_age_seconds=min_age_seconds)
            require(current["token"] == expected_token,
                    "Temporary cleanup plan changed; inspect again")
            if current["count"]:
                self._ensure_history()
                require(not self.quarantine.is_symlink() and
                        (not self.quarantine.exists() or self.quarantine.is_dir()),
                        "Unsafe quarantine directory")
                self.quarantine.mkdir(exist_ok=True)
            moved = []
            for file in current["files"]:
                source = self.path.parent / file["name"]
                require(_regular(source) and _sha(source) == file["sha256"],
                        "Temporary file changed during cleanup")
                destination = self.quarantine / (file["name"] + "." +
                                                  str(time.time_ns()))
                require(not destination.exists(), "Quarantine destination exists")
                os.replace(source, destination)
                moved.append(destination.name)
            return {"moved": moved, "preserved": True, "count": len(moved)}
