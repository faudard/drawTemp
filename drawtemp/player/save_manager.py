"""R12.10 Player checkpoint catalogue and crash-safe autosave.

All generations are canonical GameSession v1 records written via the R1.8
PlayerSlotStore. No gameplay metadata is added to session records or rules.
"""
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from drawtemp.sdk.slots import PlayerSlotStore, SlotError


class SaveManager:
    """Validated autosave + manual slots, with explicit recovery actions.

    A valid primary is never silently replaced by a backup. The Continue
    action chooses the newest *verified primary*; damaged sources remain on
    disk and are described in the UI for explicit recovery.
    """

    def __init__(self, directory, content, project, campaign_id):
        self.directory = Path(directory)
        self.content = content
        self.project = project
        self.campaign_id = campaign_id
        self.auto_path = self.directory / "autosave.json"
        self._cache_signature = None
        self._cache = None
        self._mutex = RLock()

    def _store(self, source):
        if source == "auto":
            path = self.auto_path
        elif type(source) is int and 1 <= source <= self.project.save_slots:
            path = self.directory / ("slot_" + str(source) + ".json")
        else:
            raise ValueError("Unknown save source")
        return PlayerSlotStore(path, self.content, self.project,
                               campaign_id=self.campaign_id)

    def _signature(self):
        # lstat catches symlink replacement; changes on disk invalidate the
        # in-process cache even when another process edits a checkpoint.
        result = []
        for source in ("auto", *range(1, self.project.save_slots + 1)):
            base = self._store(source).path
            for file in (base, base.with_suffix(".json.bak")):
                try:
                    st = file.lstat()
                    result.append((file.name, st.st_size, st.st_mtime_ns,
                                   st.st_mode, st.st_ino))
                except FileNotFoundError:
                    result.append((file.name, None))
        return tuple(result)

    def _invalidate(self):
        self._cache_signature = None
        self._cache = None

    def catalog(self):
        """Read-only inspection; no repair and no backup promotion."""
        with self._mutex:
            signature = self._signature()
            if self._cache is not None and signature == self._cache_signature:
                # UI consumers receive detached data.
                from copy import deepcopy
                return deepcopy(self._cache)
            rows = []
            for source in ("auto", *range(1, self.project.save_slots + 1)):
                store = self._store(source)
                info = store.inspect()
                mtime = store.path.stat().st_mtime_ns if (
                    info.primary == "valid" and not store.path.is_symlink()) else 0
                rows.append({
                    "source": source, "status": info.primary,
                    "backup_status": info.backup,
                    "recoverable": info.recoverable,
                    "error": info.message[:400],
                    "mtime_ns": mtime,
                    "saved_at": (datetime.fromtimestamp(
                        mtime / 1_000_000_000, tz=timezone.utc
                    ).isoformat(timespec="seconds") if mtime else ""),
                })
            candidates = [row for row in rows if row["status"] == "valid"]
            latest = max(candidates, key=lambda r: (
                r["mtime_ns"], r["source"] == "auto"), default=None)
            invalid = [row for row in rows if row["status"] == "invalid"]
            catalog = {
                "autosave": rows[0],
                "sources": rows,
                "continue_available": latest is not None,
                "continue_source": latest["source"] if latest else None,
                "continue_label": (
                    "Autosauvegarde" if latest and latest["source"] == "auto"
                    else "Emplacement " + str(latest["source"]) if latest else ""),
                "has_invalid": bool(invalid),
                "warnings": [
                    ("Autosauvegarde" if row["source"] == "auto"
                     else "Emplacement " + str(row["source"])) +
                    " : fichier invalide, restauration manuelle possible" if row["recoverable"]
                    else ("Autosauvegarde" if row["source"] == "auto"
                          else "Emplacement " + str(row["source"])) +
                         " : fichier invalide"
                    for row in invalid
                ],
            }
            self._cache_signature = signature
            self._cache = catalog
            from copy import deepcopy
            return deepcopy(catalog)

    def autosave(self, session):
        """Verified atomic checkpoint. Never replaces a corrupt generation."""
        with self._mutex:
            self._store("auto").save(session)
            self._invalidate()
            return self.auto_path

    def resume(self):
        """Return newest verified primary; callers assign live session last.

        A race/corrupt candidate after inspection raises; never silently loads
        a backup or reverts to an older unrelated snapshot.
        """
        selected = self.catalog()["continue_source"]
        if selected is None:
            raise SlotError("no_valid_save", "Aucune sauvegarde valide à reprendre")
        return self._store(selected).load(), selected

    def load_autosave(self):
        return self._store("auto").load()

    def restore_autosave_backup(self):
        """Recovery only: refuse to downgrade an already valid autosave."""
        with self._mutex:
            inspection = self._store("auto").inspect()
            if inspection.primary == "valid":
                raise SlotError("primary_valid",
                                "Autosauvegarde principale valide : rien à restaurer")
            if inspection.backup != "valid":
                raise SlotError("backup_invalid", "Aucun secours valide disponible")
            restored = self._store("auto").restore_backup()
            self._invalidate()
            return restored
