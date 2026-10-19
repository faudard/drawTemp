"""R30.4 — conservative, headless Content/GameProject semantic review.

Only top-level missions are matched by stable ID. All other arrays (event order,
choices, unit order, layers and action sequences) are atomic to avoid corrupting
their semantics. Three-way merging never writes to the project.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

_MISSING = object()

# R48.A opt-in: these ordered resource collections have stable entity IDs.
# Legacy R30 review remains conservative unless explicitly requested.
_TYPED_SEQUENCES = frozenset((
    "/project/story/scenes",
    "/project/campaigns",
    "/project/cinematics",
))



@dataclass(frozen=True)
class Change:
    path: str
    kind: str
    before: object
    after: object

    def to_dict(self):
        return {"path": self.path, "kind": self.kind,
                "before": deepcopy(self.before), "after": deepcopy(self.after)}


@dataclass(frozen=True)
class Conflict:
    path: str
    base: object
    local: object
    incoming: object

    def to_dict(self):
        return {"path": self.path, "base": deepcopy(self.base),
                "local": deepcopy(self.local),
                "incoming": deepcopy(self.incoming)}


@dataclass(frozen=True)
class MergePreview:
    local_changes: tuple[Change, ...]
    incoming_changes: tuple[Change, ...]
    conflicts: tuple[Conflict, ...]
    content: dict | None
    project: dict | None
    local_fingerprint: str
    candidate_fingerprint: str | None

    @property
    def can_apply(self) -> bool:
        return not self.conflicts and self.content is not None and self.project is not None


def _document(value):
    result = value.to_dict() if hasattr(value, "to_dict") else deepcopy(value)
    if not isinstance(result, dict):
        raise ValueError("Expected canonical document dictionary")
    return deepcopy(result)


def _pointer(parent: str, key: str) -> str:
    return parent + "/" + str(key).replace("~", "~0").replace("/", "~1")


def _value(value):
    return {"$missing": True} if value is _MISSING else deepcopy(value)


def _mission_index(value):
    if not isinstance(value, list):
        return None
    result = {}
    for row in value:
        if (not isinstance(row, dict) or not isinstance(row.get("id"), str) or
                not row["id"] or row["id"] in result):
            return None
        result[row["id"]] = row
    return result


def _diff(before, after, path, changes, *, typed_sequences=False):
    if before == after:
        return
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() | after.keys()):
            _diff(before.get(key, _MISSING), after.get(key, _MISSING),
                  _pointer(path, key), changes, typed_sequences=typed_sequences)
        return
    if path == "/content/missions" or (typed_sequences and path in _TYPED_SEQUENCES):
        left, right = _mission_index(before), _mission_index(after)
        if left is not None and right is not None:
            for key in sorted(left.keys() | right.keys()):
                _diff(left.get(key, _MISSING), right.get(key, _MISSING),
                      _pointer(path, key), changes, typed_sequences=typed_sequences)
            before_ids = [row["id"] for row in before]
            after_ids = [row["id"] for row in after]
            if before_ids != after_ids:
                changes.append(Change(_pointer(path, "@order"), "reorder",
                                      before_ids, after_ids))
            return
    kind = ("add" if before is _MISSING else
            "delete" if after is _MISSING else "replace")
    changes.append(Change(path, kind, _value(before), _value(after)))


def semantic_diff(before_content, before_project, after_content, after_project,
                  *, typed_sequences=False) -> tuple[Change, ...]:
    """Return detached changes, keyed by stable ID for approved resource lists."""
    changes = []
    for name, before, after in (
            ("content", before_content, after_content),
            ("project", before_project, after_project)):
        _diff(_document(before), _document(after), "/" + name, changes,
              typed_sequences=typed_sequences)
    return tuple(sorted(changes, key=lambda change: (change.path, change.kind)))


def _merge(base, local, incoming, path, conflicts, choices=None, *, typed_sequences=False):
    # These cases also handle new properties and deletions without resurrecting
    # removed keys or silently overwriting an independent edit.
    if local == incoming:
        return deepcopy(local) if local is not _MISSING else _MISSING
    if local == base:
        return deepcopy(incoming) if incoming is not _MISSING else _MISSING
    if incoming == base:
        return deepcopy(local) if local is not _MISSING else _MISSING

    if all(isinstance(value, dict) for value in (base, local, incoming)):
        result = {}
        for key in sorted(base.keys() | local.keys() | incoming.keys()):
            value = _merge(base.get(key, _MISSING),
                           local.get(key, _MISSING),
                           incoming.get(key, _MISSING),
                           _pointer(path, key), conflicts, choices,
                           typed_sequences=typed_sequences)
            if value is not _MISSING:
                result[key] = value
        return result

    # Reordering, deleting or adding missions concurrently is intentionally
    # atomic. With equal IDs/order, independent mission fields can merge.
    if path == "/content/missions":
        maps = [_mission_index(value) for value in (base, local, incoming)]
        if all(item is not None for item in maps):
            orders = [[row["id"] for row in value]
                      for value in (base, local, incoming)]
            if orders[0] == orders[1] == orders[2]:
                return [_merge(maps[0][name], maps[1][name], maps[2][name],
                               _pointer(path, name), conflicts, choices,
                               typed_sequences=typed_sequences)
                        for name in orders[0]]
    if typed_sequences and path in _TYPED_SEQUENCES:
        maps = [_mission_index(value) for value in (base, local, incoming)]
        if all(item is not None for item in maps):
            base_ids, local_ids, incoming_ids = (
                [row["id"] for row in value] for value in (base, local, incoming))
            # An independent append is safe. Inserting before existing entities,
            # removing/reordering them or replacing an ID is *not* inferred.
            if (local_ids[:len(base_ids)] == base_ids and
                    incoming_ids[:len(base_ids)] == base_ids):
                order = base_ids + local_ids[len(base_ids):] + [
                    key for key in incoming_ids[len(base_ids):]
                    if key not in maps[1]]
                result = []
                for key in order:
                    value = _merge(
                        maps[0].get(key, _MISSING),
                        maps[1].get(key, _MISSING),
                        maps[2].get(key, _MISSING),
                        _pointer(path, key), conflicts, choices,
                        typed_sequences=typed_sequences)
                    if value is not _MISSING:
                        result.append(value)
                return result
    if choices is not None and path in choices:
        value = local if choices[path] == "local" else incoming
        return _MISSING if value is _MISSING else deepcopy(value)
    conflicts.append(Conflict(path, _value(base), _value(local), _value(incoming)))
    return _MISSING


def fingerprint_pair(content, project) -> str:
    raw = json.dumps({"content": _document(content), "project": _document(project)},
                     sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def preview_merge(base_content, base_project,
                  local_content, local_project,
                  incoming_content, incoming_project, *, typed_sequences=False) -> MergePreview:
    """Perform a no-side-effect three-way preview; never guess conflict resolution."""
    b_content, b_project = _document(base_content), _document(base_project)
    l_content, l_project = _document(local_content), _document(local_project)
    r_content, r_project = _document(incoming_content), _document(incoming_project)
    conflicts = []
    content = _merge(b_content, l_content, r_content, "/content", conflicts,
                     typed_sequences=typed_sequences)
    project = _merge(b_project, l_project, r_project, "/project", conflicts,
                     typed_sequences=typed_sequences)
    return MergePreview(
        semantic_diff(b_content, b_project, l_content, l_project,
                      typed_sequences=typed_sequences),
        semantic_diff(b_content, b_project, r_content, r_project,
                      typed_sequences=typed_sequences),
        tuple(sorted(conflicts, key=lambda entry: entry.path)),
        deepcopy(content) if not conflicts else None,
        deepcopy(project) if not conflicts else None,
        fingerprint_pair(l_content, l_project),
        fingerprint_pair(content, project) if not conflicts else None,
    )


def stage_merge(session, preview: MergePreview, *, expected_revision: int):
    """Stage for the existing R1 AuthoringSession preview/apply/Undo transaction.

    Returns an AuthoringPlan; the caller must review and explicitly apply it.
    Both the session revision and exact local document fingerprint are checked.
    """
    if not isinstance(preview, MergePreview) or not preview.can_apply:
        raise ValueError("Unresolved or invalid merge preview")
    if fingerprint_pair(preview.content, preview.project) != preview.candidate_fingerprint:
        raise ValueError("Merge candidate changed after review")
    snapshot = session.snapshot()
    if (snapshot.revision != expected_revision or
            fingerprint_pair(snapshot.to_dict()["content"],
                             snapshot.to_dict()["project"]) != preview.local_fingerprint):
        raise ValueError("Stale merge review; refresh before applying")
    return session.preview_pair(
        lambda _content, _project: (deepcopy(preview.content),
                                    deepcopy(preview.project)),
        kind="r30-semantic-merge",
    )



def resolve_merge(base_content, base_project,
                  local_content, local_project,
                  incoming_content, incoming_project, decisions,
                  *, typed_sequences=False) -> MergePreview:
    """Resolve *every* detected three-way conflict by explicit local/incoming choice.

    This is an isolated preview; no source file or AuthoringSession is changed.
    Choosing a whole conflicting sequence is intentional: ordered event actions
    and mission ordering cannot be merged element-by-element without semantics.
    """
    initial = preview_merge(base_content, base_project,
                            local_content, local_project,
                            incoming_content, incoming_project,
                            typed_sequences=typed_sequences)
    if not isinstance(decisions, dict):
        raise ValueError("Conflict resolutions must be a path-to-choice dictionary")
    paths = {conflict.path for conflict in initial.conflicts}
    if set(decisions) != paths:
        raise ValueError("One explicit decision is required for each conflict")
    if any(choice not in ("local", "incoming") for choice in decisions.values()):
        raise ValueError("Resolution must be local or incoming")
    if not paths:
        return initial
    b_content, b_project = _document(base_content), _document(base_project)
    l_content, l_project = _document(local_content), _document(local_project)
    r_content, r_project = _document(incoming_content), _document(incoming_project)
    unresolved = []
    content = _merge(b_content, l_content, r_content, "/content", unresolved,
                     decisions, typed_sequences=typed_sequences)
    project = _merge(b_project, l_project, r_project, "/project", unresolved,
                     decisions, typed_sequences=typed_sequences)
    if unresolved or not isinstance(content, dict) or not isinstance(project, dict):
        raise ValueError("Resolution could not construct canonical documents")
    return MergePreview(initial.local_changes, initial.incoming_changes,
                        (), deepcopy(content), deepcopy(project),
                        initial.local_fingerprint, fingerprint_pair(content, project))
