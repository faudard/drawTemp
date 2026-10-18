"""R1.B: headless transactional authoring facade for the Qt Studio.

Wraps the existing Content/GameProject validators, typed map commands, Studio
history and two-file recovery store. It is not a second content schema, a
renderer, or a replacement for GameSession.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
import json
from pathlib import Path

from drawtemp.core import GameProject, RuleError
from drawtemp.sdk.simulation import freeze, thaw
from sporebound.editor_views import ALL_VIEWS
from sporebound.studio_transaction import (
    StudioHistory, StudioTransactionStore, validate_pair,
)


class AuthoringError(RuleError):
    """Stable machine-readable code and operation for UI diagnostics."""

    def __init__(self, code: str, operation: str, message: str):
        self.code = code
        self.operation = operation
        super().__init__(message)


@dataclass(frozen=True)
class AuthoringSnapshot:
    revision: int
    content: Mapping
    project: Mapping
    dirty: bool
    can_undo: bool
    can_redo: bool

    def to_dict(self):
        return {
            "revision": self.revision,
            "content": thaw(self.content),
            "project": thaw(self.project),
            "dirty": self.dirty,
            "can_undo": self.can_undo,
            "can_redo": self.can_redo,
        }


@dataclass(frozen=True)
class AuthoringPlan:
    """Detached validated edit. Only the originating handle may commit it."""

    source_revision: int
    kind: str
    mission_id: str | None
    views: tuple[str, ...]
    content: Mapping
    project: Mapping
    _owner: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class AuthoringTransition:
    source_revision: int
    snapshot: AuthoringSnapshot
    kind: str
    mission_id: str | None
    views: tuple[str, ...]


class AuthoringSession:
    """Single-owner editor state using the canonical two-document history.

    Commands run on detached dictionaries. A preview never commits; an apply
    validates both documents and then records exactly one undo transaction.
    Revisions protect against stale previews, including edit→undo ABA.
    Notifications are represented by the returned transition, not Qt signals.
    Consumers must marshal them to the GUI thread themselves.
    """

    def __init__(self, content, project, *, history_limit=50):
        data = content.to_dict() if hasattr(content, "to_dict") else deepcopy(content)
        manifest = project.to_dict() if isinstance(project, GameProject) else deepcopy(project)
        self._content, self._project = validate_pair(data, manifest)
        self._history = StudioHistory(self._content, self._project, limit=history_limit)
        self._revision = 0
        self._identity = object()
        self._saved = (deepcopy(self._content), deepcopy(self._project))
        self._store = None
        self._disk_revision = None

    @classmethod
    def new(cls, content, project, *, history_limit=50):
        return cls(content, project, history_limit=history_limit)

    @classmethod
    def open(cls, content_path, *, history_limit=50):
        store = StudioTransactionStore(content_path)
        if store.pending:
            raise AuthoringError("recovery_required", "open",
                                 "An interrupted two-file save requires explicit recovery")
        if not all(path.is_file() for path in store.paths):
            raise AuthoringError("missing_document", "open",
                                 "Both Content and GameProject files are required")
        try:
            expected = store.revisions()
            content = json.loads(store.content_path.read_text(encoding="utf-8"))
            project = json.loads(store.project_path.read_text(encoding="utf-8"))
            if store.revisions() != expected:
                raise AuthoringError("external_change", "open",
                                     "The project changed during loading")
            result = cls(content, project, history_limit=history_limit)
        except AuthoringError:
            raise
        except (ValueError, UnicodeError, OSError) as exc:
            raise AuthoringError("invalid_document", "open", str(exc)) from exc
        result._store = store
        result._disk_revision = expected
        return result

    @classmethod
    def recover(cls, content_path, choice, *, history_limit=50):
        """Recovery is explicit; never silently overwrite a user's project."""
        store = StudioTransactionStore(content_path)
        store.recover(choice)  # Canonical complete/rollback validation.
        return cls.open(content_path, history_limit=history_limit)

    @property
    def revision(self):
        return self._revision

    def snapshot(self):
        return AuthoringSnapshot(
            self._revision, freeze(self._content), freeze(self._project),
            (self._content, self._project) != self._saved,
            self._history.can_undo, self._history.can_redo,
        )

    def _preview_pair(self, transform, *, kind, mission_id=None, views=ALL_VIEWS):
        if not isinstance(kind, str) or not kind:
            raise AuthoringError("invalid_command", "preview", "A command kind is required")
        if mission_id is not None and (
                not isinstance(mission_id, str) or
                mission_id not in {row["id"] for row in self._content["missions"]}):
            raise AuthoringError("unknown_mission", "preview", str(mission_id))
        views = tuple(dict.fromkeys(views))
        if not views or any(view not in ALL_VIEWS for view in views):
            raise AuthoringError("invalid_views", "preview", "Unknown presentation view")
        before_revision = self._revision
        try:
            result = transform(deepcopy(self._content), deepcopy(self._project))
            if not isinstance(result, tuple) or len(result) != 2:
                raise RuleError("An edit must return (Content, GameProject)")
            content, project = validate_pair(*result)
        except (RuleError, ValueError, TypeError, KeyError) as exc:
            raise AuthoringError("invalid_edit", "preview", str(exc)) from exc
        if before_revision != self._revision:
            raise AuthoringError("stale_revision", "preview",
                                 "The editor changed during validation")
        return AuthoringPlan(
            before_revision, kind, mission_id, views,
            freeze(content), freeze(project), self._identity,
        )

    def preview(self, command, mission_id):
        """Preview an existing TypedEditCommand; no separate command schema."""
        kind = getattr(command, "kind", None)
        views = getattr(command, "views", ())
        if not callable(getattr(command, "transform", None)):
            raise AuthoringError("invalid_command", "preview", "Expected TypedEditCommand")
        return self._preview_pair(
            lambda content, project: (command.transform(content, mission_id), project),
            kind=kind, mission_id=mission_id, views=views,
        )

    def preview_project(self, transform: Callable, *, kind="project"):
        """Edit GameProject alone using a trusted, pure headless transformer."""
        if not callable(transform):
            raise AuthoringError("invalid_command", "preview", "Expected project transformer")
        return self._preview_pair(
            lambda content, project: (content, transform(project)),
            kind=kind, views=("workspace", "inspector"),
        )

    def preview_pair(self, transform: Callable, *, kind="project-and-content",
                     mission_id=None, views=ALL_VIEWS):
        """Atomic cross-document authoring (e.g. event ↔ cinematic)."""
        if not callable(transform):
            raise AuthoringError("invalid_command", "preview", "Expected pair transformer")
        return self._preview_pair(transform, kind=kind, mission_id=mission_id,
                                  views=views)

    def apply(self, plan: AuthoringPlan):
        if not isinstance(plan, AuthoringPlan) or plan._owner is not self._identity:
            raise AuthoringError("foreign_preview", "apply",
                                 "Preview belongs to a different editor session")
        if plan.source_revision != self._revision:
            raise AuthoringError("stale_revision", "apply",
                                 "stale preview: the editor changed; create a new preview")
        try:
            data, project = validate_pair(thaw(plan.content), thaw(plan.project))
        except (RuleError, ValueError, TypeError, KeyError) as exc:
            raise AuthoringError("invalid_edit", "apply", str(exc)) from exc
        if (data, project) == (self._content, self._project):
            raise AuthoringError("unchanged", "apply", "The edit makes no changes")
        previous = (self._content, self._project)
        try:
            self._history.record(data, project)
            self._content, self._project = data, project
            self._revision += 1
        except Exception:
            self._content, self._project = previous
            raise
        return AuthoringTransition(
            plan.source_revision, self.snapshot(), plan.kind,
            plan.mission_id, plan.views,
        )

    def execute(self, command, mission_id):
        return self.apply(self.preview(command, mission_id))

    def _restore(self, direction):
        previous_revision = self._revision
        try:
            data, project = getattr(self._history, direction)()
            self._content, self._project = data, project.to_dict()
            self._revision += 1
        except RuleError as exc:
            raise AuthoringError("history_unavailable", direction, str(exc)) from exc
        return AuthoringTransition(previous_revision, self.snapshot(), direction,
                                   None, tuple(ALL_VIEWS))

    def undo(self):
        return self._restore("undo")

    def redo(self):
        return self._restore("redo")

    def save(self):
        if self._store is None:
            raise AuthoringError("no_destination", "save",
                                 "Use save_as for a new project")
        try:
            self._store.save(self._content, self._project,
                             expected_previous=self._disk_revision)
        except (RuleError, OSError) as exc:
            raise AuthoringError("save_failed", "save", str(exc)) from exc
        self._disk_revision = self._store.revisions()
        self._saved = (deepcopy(self._content), deepcopy(self._project))
        return tuple(self._store.paths)

    def save_as(self, content_path):
        store = StudioTransactionStore(content_path)
        if store.pending or any(path.exists() for path in store.paths):
            raise AuthoringError("destination_exists", "save_as",
                                 "Save As refuses to replace existing documents")
        try:
            store.save(self._content, self._project,
                       expected_previous=(None, None))
        except (RuleError, OSError) as exc:
            raise AuthoringError("save_failed", "save_as", str(exc)) from exc
        self._store = store
        self._disk_revision = store.revisions()
        self._saved = (deepcopy(self._content), deepcopy(self._project))
        return tuple(store.paths)
