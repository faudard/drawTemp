"""R30.D — read-only local Git snapshots for canonical Creator semantic review.

No checkout, reset, stash, staging, network, push, commit, merge driver,
extension execution or write to .git/working tree. Validated Git blobs are
passed through the existing R30.A/C merge preview and AuthoringSession.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess

from drawtemp.export.r15 import project_path
from drawtemp.sdk.semantic_review import preview_merge, resolve_merge, stage_merge
from sporebound.studio_transaction import validate_pair

_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,127}\Z")
_HEX = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_MAX_JSON = 8 * 1024 * 1024


class GitReviewError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _hash_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise GitReviewError("unsafe_worktree", "Need regular, non-symlink project documents")
    digest = sha256()
    with path.open("rb") as file:
        for piece in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(piece)
    return digest.hexdigest()


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


@dataclass(frozen=True)
class GitRevision:
    ref: str
    commit: str
    content_blob: str
    project_blob: str
    content: dict
    project: dict

    def to_dict(self):
        return {"ref": self.ref, "commit": self.commit,
                "content_blob": self.content_blob,
                "project_blob": self.project_blob}


class LocalGitProject:
    """Read a tracked Content/GameProject pair as validated, immutable blobs."""

    def __init__(self, content_path):
        self.content_path = Path(content_path).absolute()
        self.project_path = project_path(self.content_path)
        _hash_file(self.content_path)
        _hash_file(self.project_path)
        self.root = Path(self._run(self.content_path.parent,
                                   "rev-parse", "--show-toplevel").decode().strip()).resolve()
        inside = self._run(self.root, "rev-parse", "--is-inside-work-tree").strip()
        if inside != b"true":
            raise GitReviewError("not_worktree", "Bare Git repositories are not supported")
        for path in (self.content_path, self.project_path):
            if (not path.resolve().is_relative_to(self.root) or
                    path.resolve() != path or
                    not path.is_file() or path.is_symlink()):
                raise GitReviewError("unsafe_worktree", "Paired documents must be in one worktree")
        self.content_rel = self.content_path.relative_to(self.root).as_posix()
        self.project_rel = self.project_path.relative_to(self.root).as_posix()

    @staticmethod
    def _run(directory, *args):
        env = dict(os.environ)
        env.update({
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_NO_LAZY_FETCH": "1",
        })
        try:
            result = subprocess.run(
                ["git", "--no-pager", *args], cwd=directory,
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=12, check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            raise GitReviewError("git_unavailable", str(exc)) from exc
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", errors="replace").strip()
            raise GitReviewError("git_command_failed",
                                 (message or "Git returned an error")[:500])
        return result.stdout

    def resolve_ref(self, ref: str) -> str:
        if (not isinstance(ref, str) or not _REF.fullmatch(ref) or
                ".." in ref or "//" in ref or ref.endswith(("/", ".", ".lock"))):
            raise GitReviewError("invalid_ref", "Invalid Git reference")
        raw = self._run(self.root, "rev-parse", "--verify", "--end-of-options",
                        ref + "^{commit}").decode("ascii", errors="replace").strip()
        if not _HEX.fullmatch(raw):
            raise GitReviewError("invalid_ref", "Reference does not resolve to a commit")
        return raw

    def _blob(self, commit: str, relative: str) -> tuple[str, bytes]:
        # Pin to verified immutable COMMIT oid and literal tracked repo path.
        # Symlink entries (120000) and submodules (160000) are never followed.
        raw = self._run(self.root, "ls-tree", "-z", commit, "--", relative)
        entries = [entry for entry in raw.split(b"\0") if entry]
        if len(entries) != 1:
            raise GitReviewError("untracked_document", "Canonical document not present at ref")
        try:
            metadata, name = entries[0].split(b"\t", 1)
            mode, kind, oid = metadata.decode("ascii").split(" ")
        except (UnicodeError, ValueError) as exc:
            raise GitReviewError("invalid_tree", "Invalid Git tree entry") from exc
        if (name != relative.encode("utf-8") or kind != "blob" or
                mode not in ("100644", "100755") or not _HEX.fullmatch(oid)):
            raise GitReviewError("unsafe_blob", "Document must be an ordinary Git blob")
        size = self._run(self.root, "cat-file", "-s", oid).decode("ascii").strip()
        if not size.isdigit() or int(size) > _MAX_JSON:
            raise GitReviewError("oversized_blob", "Project document exceeds 8 MiB")
        data = self._run(self.root, "cat-file", "blob", oid)
        if len(data) != int(size):
            raise GitReviewError("changed_blob", "Git blob size mismatch")
        return oid, data

    def snapshot(self, ref: str) -> GitRevision:
        commit = self.resolve_ref(ref)
        content_oid, content_bytes = self._blob(commit, self.content_rel)
        project_oid, project_bytes = self._blob(commit, self.project_rel)
        try:
            content, project = validate_pair(
                json.loads(content_bytes.decode("utf-8"), object_pairs_hook=_unique_pairs),
                json.loads(project_bytes.decode("utf-8"), object_pairs_hook=_unique_pairs),
            )
        except (ValueError, UnicodeError, TypeError, KeyError, OverflowError) as exc:
            raise GitReviewError("invalid_snapshot", str(exc)) from exc
        if self.resolve_ref(ref) != commit:
            raise GitReviewError("ref_moved", "Git reference moved during preview")
        return GitRevision(ref, commit, content_oid, project_oid, content, project)

    def ensure_common_base(self, base_oid: str, incoming_oid: str, head_oid: str):
        """Require a true Git common ancestor, not a guessed semantic base."""
        for descendant in (incoming_oid, head_oid):
            try:
                self._run(self.root, "merge-base", "--is-ancestor", base_oid, descendant)
            except GitReviewError as exc:
                raise GitReviewError(
                    "unrelated_history",
                    "Base must be an ancestor of incoming and local HEAD",
                ) from exc

    def worktree_hashes(self) -> tuple[str, str]:
        return _hash_file(self.content_path), _hash_file(self.project_path)


class GitReviewController:
    """Review two local refs against the live Studio session; apply one Undo edit.

    The Git repository is *always read-only*: applying only modifies the
    AuthoringSession memory. Explicit user Save is handled by the Studio.
    """

    def __init__(self, session, content_path):
        self.session = session
        self.git = LocalGitProject(content_path)
        self.invalidate()

    def compare_refs(self, base_ref: str, incoming_ref: str):
        self.invalidate()
        local_files = self.git.worktree_hashes()
        base = self.git.snapshot(base_ref)
        incoming = self.git.snapshot(incoming_ref)
        current_head = self.git.resolve_ref("HEAD")
        self.git.ensure_common_base(base.commit, incoming.commit, current_head)
        local = self.session.snapshot().to_dict()
        review = preview_merge(
            base.content, base.project,
            local["content"], local["project"],
            incoming.content, incoming.project,
        )
        if self.git.worktree_hashes() != local_files:
            raise GitReviewError("worktree_changed", "Local files changed during review")
        self._base, self._incoming = base, incoming
        self._source_hashes = local_files
        self._head_oid = current_head
        self._local = (local["content"], local["project"])
        self._revision = local["revision"]
        self._review = review
        return review

    @property
    def refs(self) -> tuple[GitRevision, GitRevision] | None:
        if self._base is None:
            return None
        return self._base, self._incoming

    def apply(self, decisions: dict[str, str]):
        if self._review is None:
            raise GitReviewError("no_review", "Inspect Git refs before applying")
        base, incoming = self._base, self._incoming
        if (self.git.resolve_ref(base.ref) != base.commit or
                self.git.resolve_ref(incoming.ref) != incoming.commit or
                self.git.resolve_ref("HEAD") != self._head_oid):
            raise GitReviewError("ref_moved", "Git branch/tag changed; review again")
        if self.git.worktree_hashes() != self._source_hashes:
            raise GitReviewError("worktree_changed", "Local project files changed; review again")
        local_content, local_project = self._local
        candidate = resolve_merge(
            base.content, base.project,
            local_content, local_project,
            incoming.content, incoming.project,
            decisions,
        )
        plan = stage_merge(self.session, candidate, expected_revision=self._revision)
        if (self.git.resolve_ref(base.ref) != base.commit or
                self.git.resolve_ref(incoming.ref) != incoming.commit or
                self.git.resolve_ref("HEAD") != self._head_oid or
                self.git.worktree_hashes() != self._source_hashes):
            raise GitReviewError("source_changed", "Reviewed Git inputs changed; review again")
        transition = self.session.apply(plan)
        self.invalidate()
        return transition

    def invalidate(self):
        self._base = None
        self._incoming = None
        self._source_hashes = None
        self._head_oid = None
        self._local = None
        self._revision = None
        self._review = None
