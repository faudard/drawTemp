"""R48.A2: fail-closed cross-document ID refactoring for the canonical Studio.

This is a single preview/apply facade over the established R2.7 story,
campaign and map-resource planners. No text substitutions, second schema,
automatic save or rewrite of historic player save slots.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from drawtemp.sdk.authoring import AuthoringPlan, AuthoringSession
from drawtemp.sdk.semantic_review import fingerprint_pair, semantic_diff
from drawtemp.sdk.simulation import thaw
from sporebound.workspace_editing import _locate
from sporebound.workspace_refactoring import plan_coordinated_rename
from sporebound.workspace_story_refactoring import (
    plan_story_rename, story_baseline,
)


class RefactorError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class RefactorPreview:
    """A pinned canonical R1 plan and an advisory, detached impact report."""

    resource: str
    new_id: str
    revision: int
    before_digest: str
    after_digest: str
    changes: tuple
    plan: AuthoringPlan = field(repr=False, compare=False)

    @property
    def affected_paths(self):
        return tuple(change.path for change in self.changes)

    def to_dict(self):
        return {
            "resource": self.resource, "new_id": self.new_id,
            "revision": self.revision,
            "before_digest": self.before_digest,
            "after_digest": self.after_digest,
            "affected_paths": list(self.affected_paths),
        }


def preview_rename(session: AuthoringSession, resource: str, new_id: str,
                   *, project_path=None) -> RefactorPreview:
    """Preview one typed rename without touching the session or filesystem.

    IDs can be repeated in other namespaces; planners reject unsupported
    references instead of doing a global string replacement. Campaign IDs
    are save-slot namespaces and require an existing saved Studio destination.
    """
    if not isinstance(session, AuthoringSession):
        raise TypeError("AuthoringSession required")
    if (not isinstance(resource, str) or not isinstance(new_id, str) or
            not new_id or len(new_id) > 64):
        raise RefactorError("invalid_request", "Expected a resource and a safe ID")
    before = session.snapshot().to_dict()
    content, project = before["content"], before["project"]
    status = session.storage_status()

    if resource.startswith(("scene:", "campaign:")):
        if resource.startswith("campaign:"):
            if (not status["has_destination"] or status["pending"] or
                    status["external_change"]):
                raise RefactorError(
                    "unsafe_save_slots", "Open a current, saved Studio project before renaming a campaign")
            destination = Path(status["path"]).resolve()
            if project_path is not None and Path(project_path).resolve() != destination:
                raise RefactorError("wrong_destination", "Campaign path differs from the active Studio")
        else:
            destination = None
        try:
            baseline = story_baseline(project, resource)
            candidate_content, candidate_project = plan_story_rename(
                content, project, resource, baseline, new_id,
                project_path=destination)
        except (ValueError, TypeError, KeyError) as exc:
            raise RefactorError("unsupported_reference", str(exc)) from exc
    elif resource.startswith(("map_actor:", "map_object:")):
        try:
            kind, mid, old, _mission, row = _locate(content, resource)
            if kind not in ("map_actor", "map_object"):
                raise ValueError("Unsupported resource")
            baseline = json.dumps(row, sort_keys=True, ensure_ascii=True)
            candidate_content, candidate_project = plan_coordinated_rename(
                content, project, resource, baseline, new_id)
        except (ValueError, TypeError, KeyError) as exc:
            raise RefactorError("unsupported_reference", str(exc)) from exc
    else:
        raise RefactorError("unsupported_resource", "Supported: scene/campaign/map_actor/map_object")

    candidate_project = (candidate_project.to_dict()
                         if hasattr(candidate_project, "to_dict")
                         else candidate_project)
    plan = session.preview_pair(
        lambda _content, _project: (candidate_content, candidate_project),
        kind="r48.coordinated.id-rename",
    )
    changes = semantic_diff(content, project, candidate_content, candidate_project,
                            typed_sequences=True)
    if not changes:
        raise RefactorError("unchanged", "No canonical references were modified")
    return RefactorPreview(
        resource, new_id, before["revision"],
        fingerprint_pair(content, project),
        fingerprint_pair(candidate_content, candidate_project),
        changes, plan,
    )


def apply_rename(session: AuthoringSession, review: RefactorPreview):
    """Only commit the exact candidate shown at preview, as one Undo step."""
    if not isinstance(review, RefactorPreview):
        raise RefactorError("invalid_preview", "Review a rename before applying")
    snap = session.snapshot().to_dict()
    if (snap["revision"] != review.revision or
            fingerprint_pair(snap["content"], snap["project"]) != review.before_digest):
        raise RefactorError("stale_preview", "Editor changed since rename preview")
    # A dataclass frozen flag alone is not sufficient: verify the candidate
    # after review before letting the canonical owner/staleness gates apply.
    plan = review.plan
    if (not isinstance(plan, AuthoringPlan) or
            plan.source_revision != review.revision or
            fingerprint_pair(thaw(plan.content), thaw(plan.project)) != review.after_digest):
        raise RefactorError("changed_preview", "Rename candidate changed since preview")
    return session.apply(plan)
