"""3.7.21B: coordinated Studio history and recoverable two-document saves.

This is authoring-only: neither gameplay saves nor replay formats are changed.
Each target is published atomically, with a durable journal to recover a crash
between the two replacements. A filesystem cannot atomically replace two files.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path

from .game_project import GameProject
from .model import Content, RuleError, require
from .storage import json_text, write_bytes, write_json
from .tactical_rpg3 import authored_rules_for_document


def validate_pair(content_data, project_data):
    """Preflight the actual game contracts without mutating either editor."""
    content = Content.from_dict(
        content_data, rules=authored_rules_for_document(content_data))
    project = GameProject.from_dict(project_data, content)
    return content.to_dict(), project.to_dict()


class StudioHistory:
    """One bounded timeline for Content and GameProject snapshots.

    A cross-document edit calls record() once *after* both changes. Restoration
    validates both target documents before advancing the history cursor.
    """

    def __init__(self, content_data, project, *, limit=50):
        require(type(limit) is int and 1 <= limit <= 500, "Invalid history limit")
        self.limit = limit
        self.on_change = None  # Optional authoring-only recovery checkpoint hook.
        self.reset(content_data, project)

    @staticmethod
    def _snapshot(content_data, project):
        manifest = project.to_dict() if isinstance(project, GameProject) else project
        return deepcopy(content_data), deepcopy(manifest)

    def reset(self, content_data, project):
        self._states = [self._snapshot(content_data, project)]
        self._cursor = 0

    @property
    def can_undo(self):
        return self._cursor > 0

    @property
    def can_redo(self):
        return self._cursor + 1 < len(self._states)

    def record(self, content_data, project):
        state = self._snapshot(content_data, project)
        if state == self._states[self._cursor]:
            return False
        del self._states[self._cursor + 1:]
        self._states.append(state)
        if len(self._states) > self.limit + 1:
            del self._states[0]
        self._cursor = len(self._states) - 1
        if self.on_change is not None:
            self.on_change()
        return True

    def _restore(self, cursor):
        content, project = validate_pair(*self._states[cursor])
        restored_project = GameProject.from_dict(
            project, Content.from_dict(content, rules=authored_rules_for_document(content)))
        self._cursor = cursor
        if self.on_change is not None:
            self.on_change()
        return content, restored_project

    def undo(self):
        require(self.can_undo, "Aucune modification à annuler")
        return self._restore(self._cursor - 1)

    def redo(self):
        require(self.can_redo, "Aucune modification à rétablir")
        return self._restore(self._cursor + 1)


def _digest(raw):
    return sha256(raw).hexdigest() if raw is not None else None


class StudioTransactionStore:
    """Save Content + GameProject with an explicit crash-recovery journal.

    The prior raw bytes are retained as .studio-prev for forensic recovery.
    Recovery is never automatic; the caller chooses 'complete' or 'rollback'.
    Unknown external changes or damaged staging files fail closed.
    """

    VERSION = 1

    def __init__(self, content_path, project_path=None):
        self.content_path = Path(content_path).resolve()
        self.project_path = (Path(project_path).resolve() if project_path is not None
                             else self.content_path.with_suffix(".game.json"))
        require(self.content_path != self.project_path, "Content and project paths must differ")
        self.paths = (self.content_path, self.project_path)
        self.journal = self.content_path.with_name(
            self.content_path.name + ".studio-recovery.json")

    def _stage(self, path):
        return path.with_name(path.name + ".studio-next")

    def _backup(self, path):
        return path.with_name(path.name + ".studio-prev")

    @property
    def pending(self):
        return self.journal.exists()

    def revisions(self):
        """SHA-256 of the exact on-disk bytes; None means not yet created."""
        return tuple(_digest(path.read_bytes()) if path.exists() else None
                     for path in self.paths)

    def _publish_one(self, path):
        os.replace(self._stage(path), path)

    def save(self, content_data, project_data, *, expected_previous=None):
        """Reject external modifications to either document before publication.

        The editor supplies the fingerprints from the last successful load or
        save. This prevents silently overwriting work from another Studio.
        """
        require(not self.pending,
                "Enregistrement interrompu : récupérer le projet avant de réenregistrer")
        validated_content, validated_project = validate_pair(content_data, project_data)
        payloads = (json_text(validated_content).encode("utf-8"),
                    json_text(validated_project).encode("utf-8"))
        previous = tuple(p.read_bytes() if p.exists() else None for p in self.paths)
        previous_revisions = tuple(_digest(raw) for raw in previous)
        if expected_previous is not None:
            require(isinstance(expected_previous, (tuple, list)) and
                    len(expected_previous) == 2 and
                    all(x is None or isinstance(x, str) and len(x) == 64
                        for x in expected_previous), "Empreintes attendues invalides")
            require(previous_revisions == tuple(expected_previous),
                    "Les fichiers Content/GameProject ont changé sur disque. "
                    "Recharger avant de remplacer leurs modifications.")
        manifest = {
            "kind": "studio_save", "version": self.VERSION,
            "paths": [str(p) for p in self.paths],
            "previous": list(previous_revisions),
            "next": [_digest(raw) for raw in payloads],
        }
        # Stage *both* payloads and both recovery generations before journal.
        # An exception before publication changes no user-owned target file.
        for path, payload, prior in zip(self.paths, payloads, previous):
            write_bytes(self._stage(path), payload)
            if prior is not None:
                write_bytes(self._backup(path), prior)
        # A second process might edit either document during staging. In that
        # case do not start a journal or replace any user-owned target.
        require(self.revisions() == previous_revisions,
                "Les fichiers du Studio ont changé pendant la préparation de la sauvegarde.")
        write_json(self.journal, manifest)
        # Once the journal exists, retain it on ANY failure for explicit repair.
        # Check again before each replacement: concurrent modifications must
        # remain untouched, with the journal available for manual inspection.
        for index, path in enumerate(self.paths):
            expected = tuple(manifest["next"][i] if i < index
                             else previous_revisions[i] for i in range(2))
            require(self.revisions() == expected,
                    f"{path.name} ou l'autre document a été modifié pendant "
                    "la sauvegarde; récupération manuelle requise")
            self._publish_one(path)
        require(self.revisions() == tuple(manifest["next"]),
                "Un document a changé après sa publication : "
                "journal conservé pour inspection et récupération.")
        self.journal.unlink()
        for path in self.paths:
            self._stage(path).unlink(missing_ok=True)
        return self.paths

    def _manifest(self):
        require(self.pending, "Aucune récupération Studio en attente")
        try:
            data = json.loads(self.journal.read_text(encoding="utf-8"))
        except (UnicodeError, ValueError, OSError) as exc:
            raise RuleError(f"Journal de récupération illisible : {exc}") from exc
        require(isinstance(data, dict) and
                set(data) == {"kind", "version", "paths", "previous", "next"} and
                data["kind"] == "studio_save" and
                type(data["version"]) is int and data["version"] == self.VERSION,
                "Journal Studio inconnu ou incompatible")
        require(data["paths"] == [str(p) for p in self.paths],
                "Journal appartenant à un autre projet")
        for key in ("previous", "next"):
            require(isinstance(data[key], list) and len(data[key]) == 2 and
                    all(v is None or (isinstance(v, str) and len(v) == 64
                         and all(c in "0123456789abcdef" for c in v))
                        for v in data[key]),
                    "Sommes de contrôle invalides dans le journal")
        require(all(v is not None for v in data["next"]),
                "Journal sans contenus de destination")
        return data

    def recovery_fingerprints(self):
        """Detached SHA-256 consent token for both files and all journal sources.

        No state is mutated. Symlinks are refused, including dangling ones.
        The entire token is checked again before the first recovery write.
        """
        tracked = (self.journal, *self.paths,
                   *(self._stage(path) for path in self.paths),
                   *(self._backup(path) for path in self.paths))
        result = []
        for path in tracked:
            require(not path.is_symlink(),
                    "Lien symbolique interdit pendant récupération : " + path.name)
            result.append(_digest(path.read_bytes()) if path.exists() else None)
        return tuple(result)

    def _plan_recovery(self, choice):
        """Validate all inputs and the resulting Content/Project pair read-only."""
        require(choice in ("complete", "rollback"), "Choisir complete ou rollback")
        data = self._manifest()
        desired = data["next"] if choice == "complete" else data["previous"]
        sources, resulting = [], []
        for index, path in enumerate(self.paths):
            require(not path.is_symlink(),
                    "Lien symbolique interdit : " + path.name)
            current = path.read_bytes() if path.exists() else None
            actual = _digest(current)
            require(actual in (data["previous"][index], data["next"][index]),
                    f"{path.name} a été modifié depuis l'interruption : copie manuelle requise")
            if actual == desired[index]:
                sources.append(None)
                resulting.append(current)
                continue
            if desired[index] is None:
                sources.append(None)
                resulting.append(None)
                continue
            source = self._stage(path) if choice == "complete" else self._backup(path)
            require(not source.is_symlink(),
                    "Lien symbolique interdit : " + source.name)
            require(source.is_file(), f"Fichier de récupération absent : {source.name}")
            raw = source.read_bytes()
            require(_digest(raw) == desired[index],
                    f"Fichier de récupération altéré : {source.name}")
            sources.append(raw)
            resulting.append(raw)
        require(all(raw is None for raw in resulting) or
                all(raw is not None for raw in resulting),
                "Récupération incomplète : Content et GameProject doivent rester un couple")
        if resulting[0] is not None:
            try:
                validate_pair(*(json.loads(raw.decode("utf-8")) for raw in resulting))
            except (ValueError, UnicodeError, TypeError, KeyError) as exc:
                raise RuleError("Couple Content/GameProject invalide après récupération : "
                                + str(exc)) from exc
        return tuple(sources), tuple(desired)

    def inspect_recovery(self):
        """Read-only report for UI; unusable choices carry a reason, not a button."""
        self._manifest()  # Invalid or foreign journal must not be hidden.
        fingerprints = self.recovery_fingerprints()
        choices = {}
        for choice in ("complete", "rollback"):
            try:
                self._plan_recovery(choice)
            except (RuleError, OSError) as exc:
                choices[choice] = {"available": False, "reason": str(exc)[:360]}
            else:
                choices[choice] = {"available": True, "reason": ""}
        return {"content_path": str(self.content_path),
                "project_path": str(self.project_path),
                "fingerprints": fingerprints, "choices": choices}

    def recover(self, choice, *, expected_fingerprints=None):
        """Explicit, consent-bound rollback/rollforward of the canonical pair.

        Recheck the displayed review's entire fingerprint tuple before writing.
        Recoveries without a UI token remain supported for existing callers.
        """
        if expected_fingerprints is not None:
            require(type(expected_fingerprints) is tuple and
                    len(expected_fingerprints) == 7 and
                    all(item is None or
                        isinstance(item, str) and len(item) == 64
                        for item in expected_fingerprints),
                    "Confirmation de récupération invalide")
            require(self.recovery_fingerprints() == expected_fingerprints,
                    "Récupération obsolète : les fichiers ont changé depuis l'aperçu")
        sources, desired = self._plan_recovery(choice)
        # The journal stays present after a partial failure, allowing explicit
        # retry. Never discard a different user's changes without a new review.
        for index, path in enumerate(self.paths):
            raw = sources[index]
            if raw is not None:
                write_bytes(path, raw)
            elif desired[index] is None and path.exists():
                path.unlink()
        self.journal.unlink()
        for path in self.paths:
            self._stage(path).unlink(missing_ok=True)
        return self.paths
