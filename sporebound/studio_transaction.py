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
        return True

    def _restore(self, cursor):
        content, project = validate_pair(*self._states[cursor])
        self._cursor = cursor
        return content, GameProject.from_dict(
            project, Content.from_dict(content, rules=authored_rules_for_document(content)))

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

    def _publish_one(self, path):
        os.replace(self._stage(path), path)

    def save(self, content_data, project_data):
        require(not self.pending,
                "Enregistrement interrompu : récupérer le projet avant de réenregistrer")
        validated_content, validated_project = validate_pair(content_data, project_data)
        payloads = (json_text(validated_content).encode("utf-8"),
                    json_text(validated_project).encode("utf-8"))
        previous = tuple(p.read_bytes() if p.exists() else None for p in self.paths)
        manifest = {
            "kind": "studio_save", "version": self.VERSION,
            "paths": [str(p) for p in self.paths],
            "previous": [_digest(raw) for raw in previous],
            "next": [_digest(raw) for raw in payloads],
        }
        # Stage *both* payloads and both recovery generations before journal.
        # An exception before publication changes no user-owned target file.
        for path, payload, prior in zip(self.paths, payloads, previous):
            write_bytes(self._stage(path), payload)
            if prior is not None:
                write_bytes(self._backup(path), prior)
        write_json(self.journal, manifest)
        # Once the journal exists, retain it on ANY failure for explicit repair.
        for path in self.paths:
            self._publish_one(path)
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

    def recover(self, choice):
        """Explicit rollback/rollforward, idempotent after an interrupted retry.

        Validate EVERY target and EVERY needed recovery source before writing
        either target. Changes made externally after the interruption are never
        overwritten. Calling twice after success is refused (no pending journal).
        """
        require(choice in ("complete", "rollback"), "Choisir complete ou rollback")
        data = self._manifest()
        desired = data["next"] if choice == "complete" else data["previous"]
        sources = []
        for index, path in enumerate(self.paths):
            actual = _digest(path.read_bytes()) if path.exists() else None
            require(actual in (data["previous"][index], data["next"][index]),
                    f"{path.name} a été modifié depuis l'interruption : copie manuelle requise")
            if actual == desired[index]:
                sources.append(None)
                continue
            if desired[index] is None:
                sources.append(None)
                continue
            source = self._stage(path) if choice == "complete" else self._backup(path)
            require(source.is_file(), f"Fichier de récupération absent : {source.name}")
            raw = source.read_bytes()
            require(_digest(raw) == desired[index],
                    f"Fichier de récupération altéré : {source.name}")
            sources.append(raw)
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
