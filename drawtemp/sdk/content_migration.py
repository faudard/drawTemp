"""R1.6: explicit, non-destructive Content/GameProject v0-envelope import.

This is NOT an automatic rewrite of historical tactical saves. Only the
version-less / version=0 envelope of the already-compatible v1 document
structure is supported; unknown data shapes fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from drawtemp.core import Content, GameProject, RuleError
from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.simulation import freeze, thaw


class MigrationError(RuleError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class MigrationPreview:
    source_content: Path
    source_project: Path
    source_hashes: tuple[str, str]
    content_version: int
    project_version: int
    target_version: int
    changes: tuple[str, ...]
    content: object
    project: object

    def to_dict(self):
        return {"source_content": str(self.source_content),
                "source_project": str(self.source_project),
                "source_hashes": list(self.source_hashes),
                "content_version": self.content_version,
                "project_version": self.project_version,
                "target_version": self.target_version,
                "changes": list(self.changes),
                "content": thaw(self.content), "project": thaw(self.project)}


def _document_version(data, label):
    if not isinstance(data, dict):
        raise MigrationError("invalid_document", label + " must be an object")
    version = data.get("version", 0)
    if type(version) is not int or version not in (0, 1):
        raise MigrationError("unsupported_version", label + " has unsupported version")
    return version


def preview_documents(content, project):
    """Validate an exact, known v0-envelope -> canonical v1 transformation.

    A v0 envelope may lack the `version` tag, but must otherwise obey the
    current v1 domain rules. We never infer/rewrite gameplay semantics.
    """
    cv, pv = _document_version(content, "Content"), _document_version(project, "GameProject")
    if not {"skills", "missions"} <= set(content) or "campaigns" not in project:
        raise MigrationError("unsupported_schema", "Only v0 envelopes containing v1 fields can be imported")
    copied_content = dict(content)
    copied_project = dict(project)
    copied_content["version"] = 1
    copied_project["version"] = 1
    try:
        validated_content = Content.from_dict(copied_content)
        validated_project = GameProject.from_dict(copied_project, validated_content)
    except (RuleError, ValueError, TypeError, KeyError) as exc:
        raise MigrationError("invalid_document", str(exc)) from exc
    changes = tuple(label for label, version in
                    (("Content.version: 0 -> 1", cv),
                     ("GameProject.version: 0 -> 1", pv)) if version == 0)
    return cv, pv, changes, freeze(validated_content.to_dict()), freeze(validated_project.to_dict())


def _read(path):
    if path.is_symlink() or not path.is_file():
        raise MigrationError("missing_source", "Expected a regular, non-symlink source: " + str(path))
    try:
        raw = path.read_bytes()
        return json.loads(raw.decode("utf-8")), sha256(raw).hexdigest()
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise MigrationError("invalid_source", str(exc)) from exc


def preview_pair(content_path):
    """Read source documents and produce a detached, immutable migration plan."""
    source = Path(content_path)
    if source.suffix != ".json" or source.name.endswith(".game.json"):
        raise MigrationError("invalid_path", "Expected a Content .json document")
    project_path = source.with_suffix(".game.json")
    content, content_hash = _read(source)
    project, project_hash = _read(project_path)
    cv, pv, changes, normalized_content, normalized_project = preview_documents(content, project)
    return MigrationPreview(source, project_path, (content_hash, project_hash),
                            cv, pv, 1, changes, normalized_content, normalized_project)


def commit_pair(plan, destination):
    """Export to a *new* canonical pair, never overwriting any source.

    Re-read the source before writing to refuse stale approvals. The canonical
    StudioTransactionStore publishes both documents with a recovery journal.
    """
    if not isinstance(plan, MigrationPreview):
        raise MigrationError("invalid_plan", "Explicit preview is required")
    target = Path(destination)
    if (target.suffix != ".json" or target.name.endswith(".game.json") or
            target == plan.source_content or
            target.with_suffix(".game.json") == plan.source_project):
        raise MigrationError("invalid_destination", "Choose a separate Content .json destination")
    if target.is_symlink() or target.with_suffix(".game.json").is_symlink():
        raise MigrationError("unsafe_destination", "Destination must not be a symlink")
    current = (_read(plan.source_content)[1], _read(plan.source_project)[1])
    if current != plan.source_hashes:
        raise MigrationError("stale_preview", "Sources changed since migration preview")
    # Re-run domain validation; never trust serialized preview data alone.
    _, _, _, normalized_content, normalized_project = preview_documents(
        thaw(plan.content), thaw(plan.project))
    if (normalized_content, normalized_project) != (plan.content, plan.project):
        raise MigrationError("invalid_plan", "Migration result differs from validated preview")
    try:
        session = AuthoringSession.new(thaw(plan.content), thaw(plan.project))
        paths = session.save_as(target)
        reopened = AuthoringSession.open(target)
    except (RuleError, AuthoringError, OSError, ValueError) as exc:
        raise MigrationError("publish_failed", str(exc)) from exc
    if (reopened.snapshot().content != plan.content or
            reopened.snapshot().project != plan.project):
        raise MigrationError("verification_failed", "Published documents failed round-trip verification")
    return tuple(paths)
