"""R30.C Qt-independent review controllers for creator packs and semantic merges.

No duplicate content registry: pack output remains R30.B's opt-in *new copy*;
merge changes are staged/applied via the original R1 AuthoringSession.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath

from drawtemp.export.pack_import import (
    _archive, import_pack_to_copy, preview_pack_import,
)
from drawtemp.export.r15 import project_path
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.semantic_review import (
    preview_merge, resolve_merge, stage_merge,
)


class ReviewError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class PackResourceRow:
    path: str
    extension: str
    kinds: tuple[str, ...]
    license: str
    origin: str
    size: int


class PackReviewController:
    """Never touches Content/GameProject until explicit, new-copy publication."""

    def __init__(self, content_path):
        self.content_path = Path(content_path).absolute()
        self._pack_path = None
        self._pack_sha = None
        self._preview = None

    def inspect(self, archive_path) -> tuple[PackResourceRow, ...]:
        self._preview = None
        self._pack_path = None
        pack_path = Path(archive_path).absolute()
        raw, manifest = _archive(pack_path)  # Same strict ZIP verification as R30.B.
        rows = []
        for entry in sorted(manifest["files"], key=lambda item: item["path"]):
            ext = PurePosixPath(entry["path"]).suffix.lower()
            kinds = (("sprite", "portrait") if ext == ".png" else
                     ("sound",) if ext in (".ogg", ".wav") else ())
            rows.append(PackResourceRow(
                entry["path"], ext, kinds, entry["license"],
                entry["origin"], entry["size"],
            ))
        self._pack_path = pack_path
        self._pack_sha = sha256(raw).hexdigest()
        return tuple(rows)

    def preview(self, choices):
        self._preview = None
        if self._pack_path is None:
            raise ReviewError("no_pack", "Inspect an archive before selecting resources")
        # R30.B checks names, IDs, types and validates the canonical candidate.
        preview = preview_pack_import(self.content_path, self._pack_path, choices)
        if preview.archive_sha256 != self._pack_sha:
            raise ReviewError("pack_changed", "Pack changed after inspection")
        self._preview = preview
        return preview

    def publish(self, destination):
        if self._preview is None:
            raise ReviewError("no_preview", "Recheck the choices before importing")
        # Includes full source, archive and asset hash revalidation.
        output = import_pack_to_copy(self._preview, destination)
        self._preview = None
        return output

    def invalidate(self):
        self._preview = None


@dataclass(frozen=True)
class _DiskPair:
    path: Path
    content_digest: str
    project_digest: str
    content: dict
    project: dict

    def unchanged(self) -> bool:
        try:
            return (_file_digest(self.path) == self.content_digest and
                    _file_digest(project_path(self.path)) == self.project_digest)
        except (OSError, ValueError):
            return False


def _file_digest(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ReviewError("unsafe_file", "Expected regular, non-symlink documents")
    return sha256(path.read_bytes()).hexdigest()


def _disk_pair(path) -> _DiskPair:
    source = Path(path).absolute()
    before = _file_digest(source), _file_digest(project_path(source))
    session = AuthoringSession.open(source)
    snapshot = session.snapshot().to_dict()
    after = _file_digest(source), _file_digest(project_path(source))
    if before != after:
        raise ReviewError("file_changed", "Document changed while reviewing it")
    return _DiskPair(source, *after, snapshot["content"], snapshot["project"])


class MergeReviewController:
    """Three-way review against paired files, on a single live AuthoringSession.

    Disk inputs are pinned by exact byte checksums. The local editor is pinned by
    R1 revision and data fingerprint. No disk write occurs on merge apply:
    saving remains an explicit action in the owning Studio shell.
    """

    def __init__(self, session: AuthoringSession):
        self.session = session
        self._base = None
        self._incoming = None
        self._review = None
        self._revision = None
        self._local = None

    def compare(self, base_path, incoming_path):
        self.invalidate()
        base = _disk_pair(base_path)
        incoming = _disk_pair(incoming_path)
        local = self.session.snapshot().to_dict()
        result = preview_merge(
            base.content, base.project,
            local["content"], local["project"],
            incoming.content, incoming.project,
        )
        self._base, self._incoming = base, incoming
        self._review = result
        self._revision = local["revision"]
        self._local = (local["content"], local["project"])
        return result

    def apply(self, decisions: dict[str, str]):
        if self._review is None or self._base is None or self._incoming is None:
            raise ReviewError("no_review", "Compare files before applying a merge")
        if not self._base.unchanged() or not self._incoming.unchanged():
            raise ReviewError("external_change", "A reviewed file changed; compare again")
        base, incoming = self._base, self._incoming
        local_content, local_project = self._local
        candidate = resolve_merge(
            base.content, base.project,
            local_content, local_project,
            incoming.content, incoming.project,
            decisions,
        )
        plan = stage_merge(self.session, candidate, expected_revision=self._revision)
        # Detect inputs replaced during candidate validation.
        if not base.unchanged() or not incoming.unchanged():
            raise ReviewError("external_change", "Reviewed files changed during validation")
        result = self.session.apply(plan)
        self.invalidate()
        return result

    def invalidate(self):
        self._base = None
        self._incoming = None
        self._review = None
        self._revision = None
        self._local = None
