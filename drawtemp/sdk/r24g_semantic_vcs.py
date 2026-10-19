"""R24.G: fail-closed semantic three-way merge for canonical Content/GameProject.

This module is a detached authoring adapter. It does not implement another
Content/GameProject registry, gameplay engine, git client, or save protocol.
All merged documents must pass the existing validate_pair contract and the
only commit path is AuthoringSession.preview_pair/apply.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path

from sporebound.studio_transaction import validate_pair
from .authoring import AuthoringPlan, AuthoringSession

SCHEMA = 1
MAX_DIFF = 2048
MAX_CONFLICTS = 256
MAX_DOCUMENT_BYTES = 16 * 1024 * 1024

# Lists without well-defined identity are intentionally atomic. Unversioned
# reorder operations on identified collections are conflicts, not silent loss.
BY_ID = frozenset({
    "skills", "missions", "units", "objects", "triggers",
    "campaigns", "sieges", "cinematics", "scenes", "choices",
})
BY_CELL = frozenset({"tiles"})
MERGEABLE_NEW_MAPS = frozenset({
    "extensions", "story", "assets", "world", "exploration",
    "campaign_flow", "jobs", "equipment", "archetypes",
})
_MISSING = object()


class SemanticMergeError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise SemanticMergeError(code, message)


def _hash(value):
    if value is _MISSING:
        return None
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise SemanticMergeError("invalid_json", "Expected finite, portable JSON values") from exc
    return sha256(encoded).hexdigest()


def _token(value):
    return str(value).replace("~", "~0").replace("/", "~1").replace("]", "~2")


def _path(parts):
    return "/" + "/".join(parts)


def _list_identity(path):
    field = path[-1] if path else ""
    if field in BY_ID:
        return "id"
    if field in BY_CELL and len(path) >= 2 and path[-2] == "board":
        return "pos"
    return None


def _keyed(rows, identity, path):
    if type(rows) is not list:
        _fail("invalid_list", "Expected array at " + _path(path))
    output, order = {}, []
    for row in rows:
        if type(row) is not dict or identity not in row:
            _fail("invalid_identity", "Missing " + identity + " at " + _path(path))
        raw = row[identity]
        if identity == "pos":
            if (type(raw) not in (list, tuple) or len(raw) != 2 or
                    any(type(n) is not int or n < 0 for n in raw)):
                _fail("invalid_identity", "Tile position must be two nonnegative integers")
            key = str(raw[0]) + "," + str(raw[1])
        else:
            if type(raw) is not str or not raw or len(raw) > 128:
                _fail("invalid_identity", "Entity id must be 1..128 characters")
            key = raw
        if key in output:
            _fail("duplicate_identity", "Duplicate key at " + _path(path))
        output[key] = row
        order.append(key)
    return output, order


def _item_path(path, identity, key):
    return path[:-1] + (path[-1] + "[" + identity + "=" + _token(key) + "]",)


def _semantic_diff(before, after, path, out):
    if before == after:
        return
    if len(out) >= MAX_DIFF:
        _fail("diff_limit", "More than 2048 semantic changes; split the merge")
    if before is _MISSING or after is _MISSING:
        operation = "added" if before is _MISSING else "removed"
        out.append({"path": _path(path), "op": operation,
                    "before_sha256": _hash(before), "after_sha256": _hash(after)})
        return
    if type(before) is dict and type(after) is dict:
        for key in sorted(set(before) | set(after)):
            _semantic_diff(before.get(key, _MISSING), after.get(key, _MISSING),
                           path + (_token(key),), out)
        return
    identity = _list_identity(path)
    if identity and type(before) is list and type(after) is list:
        left, order_a = _keyed(before, identity, path)
        right, order_b = _keyed(after, identity, path)
        common = set(order_a) & set(order_b)
        if [x for x in order_a if x in common] != [x for x in order_b if x in common]:
            out.append({"path": _path(path), "op": "reordered",
                        "before_sha256": _hash(order_a), "after_sha256": _hash(order_b)})
        for key in sorted(set(left) | set(right)):
            _semantic_diff(left.get(key, _MISSING), right.get(key, _MISSING),
                           _item_path(path, identity, key), out)
        return
    out.append({"path": _path(path), "op": "changed",
                "before_sha256": _hash(before), "after_sha256": _hash(after)})


def _check_pair(value):
    if type(value) is not dict or set(value) != {"content", "project"}:
        _fail("invalid_pair", "Expected {content, project}, two canonical JSON objects")
    try:
        content, project = validate_pair(value["content"], value["project"])
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise SemanticMergeError("invalid_pair", str(exc)) from exc
    return {"content": content, "project": project}


def semantic_diff(before, after):
    """Normalized, identity-aware diff. Never exposes entire asset payloads."""
    left, right = _check_pair(before), _check_pair(after)
    changes = []
    _semantic_diff(left, right, (), changes)
    return {"kind": "r24g-semantic-diff", "schema": SCHEMA,
            "before_sha256": _hash(left), "after_sha256": _hash(right),
            "changes": changes, "count": len(changes)}


def _conflict(path, code, base, ours, theirs, output):
    if len(output) >= MAX_CONFLICTS:
        _fail("conflict_limit", "More than 256 conflicts; split the merge")
    output.append({"path": _path(path), "reason": code,
                   "base_sha256": _hash(base), "ours_sha256": _hash(ours),
                   "theirs_sha256": _hash(theirs)})
    return _MISSING


def _three_way(base, ours, theirs, path, issues):
    if ours == theirs:
        return deepcopy(ours) if ours is not _MISSING else _MISSING
    if ours == base:
        return deepcopy(theirs) if theirs is not _MISSING else _MISSING
    if theirs == base:
        return deepcopy(ours) if ours is not _MISSING else _MISSING
    if ours is _MISSING or theirs is _MISSING:
        return _conflict(path, "delete_vs_edit", base, ours, theirs, issues)
    # Allow two branches to create distinct namespace keys in an optional
    # empty dictionary; a SAME-namespace add/add still conflicts at that key.
    if (base is _MISSING and type(ours) is dict and type(theirs) is dict
            and path and path[-1] in MERGEABLE_NEW_MAPS):
        base = {}
    elif base is _MISSING:
        return _conflict(path, "concurrent_add", base, ours, theirs, issues)
    if type(base) is dict and type(ours) is dict and type(theirs) is dict:
        output = {}
        for key in sorted(set(base) | set(ours) | set(theirs)):
            result = _three_way(base.get(key, _MISSING), ours.get(key, _MISSING),
                                theirs.get(key, _MISSING), path + (_token(key),), issues)
            if result is not _MISSING:
                output[key] = result
        return output
    identity = _list_identity(path)
    if identity and all(type(v) is list for v in (base, ours, theirs)):
        before, base_order = _keyed(base, identity, path)
        local, our_order = _keyed(ours, identity, path)
        remote, their_order = _keyed(theirs, identity, path)
        # The relative order of all retained base entities must be preserved.
        # Otherwise there is no safe consensus position for simultaneous
        # insertions/edits, so do not silently discard the reordering.
        common = set(base_order) & set(our_order) & set(their_order)
        ordered = [key for key in base_order if key in common]
        if ([key for key in our_order if key in common] != ordered or
                [key for key in their_order if key in common] != ordered):
            return _conflict(path, "reorder_unsupported", base, ours, theirs, issues)
        resolved = {}
        for key in sorted(set(before) | set(local) | set(remote)):
            changed = _three_way(before.get(key, _MISSING),
                                 local.get(key, _MISSING),
                                 remote.get(key, _MISSING),
                                 _item_path(path, identity, key), issues)
            if changed is not _MISSING:
                resolved[key] = changed
        # Keep base order for surviving entities; append disjoint new items
        # in sorted identity order, independent of dictionary insertion order.
        keys = [key for key in base_order if key in resolved]
        keys.extend(sorted(set(resolved) - set(before)))
        return [resolved[key] for key in keys]
    return _conflict(path, "concurrent_edit", base, ours, theirs, issues)


def preview_three_way(base, ours, theirs):
    """Detached preview, with every conflict identified and no partial merge.

    A structurally merged but invalid gameplay result is rejected by the
    canonical Content+GameProject validator, never returned as a valid plan.
    """
    ancestor, local, remote = _check_pair(base), _check_pair(ours), _check_pair(theirs)
    local_diff, remote_diff = semantic_diff(ancestor, local), semantic_diff(ancestor, remote)
    problems = []
    merged = _three_way(ancestor, local, remote, (), problems)
    if not problems:
        try:
            merged = _check_pair(merged)
        except SemanticMergeError as exc:
            problems.append({"path": "/", "reason": "invalid_canonical_merge",
                             "detail": str(exc),
                             "base_sha256": _hash(ancestor),
                             "ours_sha256": _hash(local),
                             "theirs_sha256": _hash(remote)})
    return {
        "kind": "r24g-three-way-preview", "schema": SCHEMA,
        "base_sha256": _hash(ancestor), "ours_sha256": _hash(local),
        "theirs_sha256": _hash(remote),
        "can_merge": not problems,
        "conflicts": problems,
        "local_diff": local_diff["changes"],
        "remote_diff": remote_diff["changes"],
        "merged_sha256": _hash(merged) if not problems else None,
        "merged": deepcopy(merged) if not problems else None,
        "note": "A preview never modifies source files or the live editor",
    }


@dataclass(frozen=True)
class MergeReview:
    """Preview report is detached; only the editor-owned plan is committable."""
    report: dict = field(compare=False)
    plan: AuthoringPlan | None = field(default=None, repr=False, compare=False)

    @property
    def can_apply(self):
        return self.report["can_merge"] and self.plan is not None


def preview_merge(session: AuthoringSession, base, theirs):
    """Bind a three-way review to exactly one live editor revision."""
    if not isinstance(session, AuthoringSession):
        _fail("invalid_session", "Expected canonical AuthoringSession")
    snapshot = session.snapshot()
    ours = snapshot.to_dict()
    report = preview_three_way(base, {"content": ours["content"],
                                      "project": ours["project"]}, theirs)
    report["source_revision"] = snapshot.revision
    plan = None
    if report["can_merge"] and report["merged_sha256"] != report["ours_sha256"]:
        merged = report["merged"]
        plan = session.preview_pair(
            lambda _content, _project:
                (deepcopy(merged["content"]), deepcopy(merged["project"])),
            kind="r24g-semantic-merge")
    # Do not expose mutable planned document references to callers.
    report.pop("merged", None)
    report["already_current"] = report["can_merge"] and plan is None
    return MergeReview(report=deepcopy(report), plan=plan)


def apply_merge(session: AuthoringSession, review: MergeReview):
    """An explicit user action. Delegate stale revision/ownership to SDK."""
    if not isinstance(session, AuthoringSession) or not isinstance(review, MergeReview):
        _fail("invalid_review", "Expected a live editor and R24.G review")
    if not review.can_apply:
        _fail("unresolved_merge", "Resolve every conflict before applying")
    return session.apply(review.plan)


def _reject_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            _fail("duplicate_json_key", "Repeated JSON key: " + key)
        out[key] = value
    return out


def _reject_nonfinite(token):
    _fail("invalid_json", "Nonfinite number in document: " + token)


def _read_json(path, *, with_hash=False):
    target = Path(path)
    if target.is_symlink() or not target.is_file():
        _fail("unsafe_path", "Expected a regular JSON document")
    try:
        with target.open("rb") as stream:
            raw = stream.read(MAX_DOCUMENT_BYTES + 1)
        if len(raw) > MAX_DOCUMENT_BYTES:
            _fail("size_limit", "Input document exceeds 16 MiB")
        data = json.loads(raw.decode("utf-8"),
                          object_pairs_hook=_reject_duplicate_keys,
                          parse_constant=_reject_nonfinite)
        return (data, sha256(raw).hexdigest()) if with_hash else data
    except SemanticMergeError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise SemanticMergeError("invalid_json", str(exc)) from exc


def read_pair(content_path):
    """Read-only sibling Content + GameProject, with stability check.

    Exactly like AuthoringSession.open, the project's filename is derived from
    the Content filename and never guessed from arbitrary project metadata.
    """
    source = Path(content_path)
    project_path = source.with_suffix(".game.json")
    if source.resolve() == project_path.resolve():
        _fail("unsafe_path", "Content and GameProject paths must differ")
    raw_content, original_content_sha = _read_json(source, with_hash=True)
    raw_project, original_project_sha = _read_json(project_path, with_hash=True)
    pair = _check_pair({"content": raw_content, "project": raw_project})
    # Even a whitespace-only concurrent edit changes the source bytes. Do not
    # silently adopt stale content as the common VCS ancestor.
    _, now_content_sha = _read_json(source, with_hash=True)
    _, now_project_sha = _read_json(project_path, with_hash=True)
    if ((original_content_sha, original_project_sha) !=
            (now_content_sha, now_project_sha)):
        _fail("external_change", "Input documents changed during validation")
    return pair
