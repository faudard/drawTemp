"""R23.C portable preview archives, bounded extraction and independent Studio/Player integrity.

This is NOT a signed MSI, notarized DMG or distro package. Runtime launch
requires no Python installation; packaging/verification utilities use stdlib.
R15 manifest and existing game saves are never changed.
"""
from __future__ import annotations

import gzip
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
from tempfile import TemporaryDirectory
import zipfile

from drawtemp.export.r15 import verify_bundle

SCHEMA = 1
KIND = "drawtemp-r23c-portable-preview"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
PLATFORMS = ("Linux", "Windows", "macOS")
MAX_FILES = 20000
MAX_MEMBER_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024 * 1024


class ReleaseError(ValueError):
    pass


def _digest(path):
    h = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _relative(value):
    if not isinstance(value, str) or "\\" in value or "\x00" in value or (
            not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value)):
        raise ReleaseError("Unsafe distribution relative path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts) or any(
            part.endswith((" ", ".")) or ":" in part for part in parts):
        raise ReleaseError("Non-portable distribution path: " + value)
    if PurePosixPath(value).as_posix() != value:
        raise ReleaseError("Non-canonical distribution path: " + value)
    return value


def _tree_files(root, *, allow_internal_symlinks=False):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ReleaseError("Distribution source is not a directory")
    paths = []
    for node in root.rglob("*"):
        if node.is_symlink():
            if not allow_internal_symlinks:
                raise ReleaseError("Symlink forbidden in portable archive: " + str(node))
            target = node.resolve(strict=True)
            if not target.is_relative_to(root):
                raise ReleaseError("Source symlink escapes runtime: " + str(node))
            # A symlink directory is copied by shutil.copytree, then the
            # resulting materialized files are verified independently.
            continue
        if node.is_file():
            paths.append(node)
        elif not node.is_dir():
            raise ReleaseError("Special filesystem entry: " + str(node))
    if len(paths) > MAX_FILES:
        raise ReleaseError("Too many distribution files")
    return sorted(paths, key=lambda p: p.relative_to(root).as_posix())


def _inventory(root):
    seen = set()
    total = 0
    out = []
    for node in _tree_files(root):
        relative = _relative(node.relative_to(root).as_posix())
        folded = relative.casefold()
        if folded in seen:
            raise ReleaseError("Case-insensitive filename collision: " + relative)
        seen.add(folded)
        size = node.stat().st_size
        if size > MAX_MEMBER_BYTES:
            raise ReleaseError("Oversized distribution member: " + relative)
        total += size
        if total > MAX_TOTAL_BYTES:
            raise ReleaseError("Distribution exceeds bounded file size")
        out.append({"path": relative, "size": size, "sha256": _digest(node),
                    "mode": stat.S_IMODE(node.stat().st_mode) & 0o777})
    return out


def verify_portable(root, *, revision=None, platform=None):
    root = Path(root).resolve(strict=True)
    ledger = root / "release.json"
    if ledger.is_symlink() or not ledger.is_file() or ledger.stat().st_size > 8 * 1024 * 1024:
        raise ReleaseError("Missing or oversized release manifest")
    try:
        def unique(pairs):
            d = {}
            for key, value in pairs:
                if key in d:
                    raise ReleaseError("Duplicate release manifest key: " + key)
                d[key] = value
            return d
        data = json.loads(ledger.read_text(encoding="utf-8"),
                          object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseError("Malformed release manifest") from exc
    if (type(data) is not dict or data.get("schema") != SCHEMA or
            data.get("kind") != KIND or data.get("platform") not in PLATFORMS or
            not isinstance(data.get("revision"), str) or
            not SHA40.fullmatch(data["revision"]) or
            data.get("certification") != "preview-NO-GO"):
        raise ReleaseError("Unsupported distribution contract")
    if platform is not None and data["platform"] != platform:
        raise ReleaseError("Distribution platform mismatch")
    if revision is not None and data["revision"] != revision:
        raise ReleaseError("Distribution revision mismatch")
    if data.get("studio") != "Studio/" + ("DrawTempStudio.exe" if data["platform"] == "Windows" else "DrawTempStudio"):
        raise ReleaseError("Missing canonical Studio executable identity")
    if data.get("game") != "Jeanne" or data.get("signature") != "not-asserted":
        raise ReleaseError("Unverified signing claim or unknown game bundle")
    game_manifest = verify_bundle(root / "Jeanne")
    if _digest(root / "Jeanne/manifest.json") != data.get("r15_manifest_sha256"):
        raise ReleaseError("Underlying R15 manifest was substituted")
    _tree_files(root)  # Includes symbolic-link / special-file rejection.
    rows = data.get("files")
    if not isinstance(rows, list) or not rows or len(rows) > MAX_FILES:
        raise ReleaseError("Invalid release file index")
    indexed = set()
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "size", "sha256", "mode"}:
            raise ReleaseError("Invalid release file entry")
        rel = _relative(row["path"])
        if rel.casefold() in indexed:
            raise ReleaseError("Duplicate distribution file")
        indexed.add(rel.casefold())
        if (not rel.startswith(("Jeanne/", "Studio/")) or
                type(row["size"]) is not int or not 0 <= row["size"] <= MAX_MEMBER_BYTES or
                type(row["mode"]) is not int or not 0 <= row["mode"] <= 0o777 or
                not isinstance(row["sha256"], str) or not SHA64.fullmatch(row["sha256"])):
            raise ReleaseError("Malformed release file index")
        file = root.joinpath(*rel.split("/"))
        if not file.is_file() or file.is_symlink() or (
                file.stat().st_size != row["size"] or _digest(file) != row["sha256"]):
            raise ReleaseError("Distribution integrity mismatch: " + rel)
    actual = {node.relative_to(root).as_posix().casefold() for node in _tree_files(root)}
    if actual != indexed | {"release.json"}:
        raise ReleaseError("Unindexed or missing distribution file")
    studio = root / data["studio"]
    if not studio.is_file() or studio.is_symlink():
        raise ReleaseError("Studio executable absent")
    if data["platform"] != "Windows" and not studio.stat().st_mode & stat.S_IXUSR:
        raise ReleaseError("Studio executable is not launchable")
    if not game_manifest["files"]:
        raise ReleaseError("Empty game bundle")
    return data


def package_preview(game, studio, destination, *, revision, platform):
    """Create a portable, unpackable *preview* and a SHA-256 digest sidecar."""
    if not isinstance(revision, str) or not SHA40.fullmatch(revision):
        raise ReleaseError("A full Git revision is required")
    if platform not in PLATFORMS:
        raise ReleaseError("Unsupported OS")
    game = Path(game).resolve(strict=True)
    studio = Path(studio).resolve(strict=True)
    game_manifest = verify_bundle(game)
    _tree_files(studio, allow_internal_symlinks=True)
    studio_exe = studio / ("DrawTempStudio.exe" if platform == "Windows" else "DrawTempStudio")
    if not studio_exe.is_file():
        raise ReleaseError("Studio native executable is missing")
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ReleaseError("Archive destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".r23c-build-", dir=destination.parent) as folder:
        root = Path(folder) / "DrawTemp"
        root.mkdir()
        # Copytree follows internal PyInstaller links and materializes files.
        shutil.copytree(game, root / "Jeanne")
        shutil.copytree(studio, root / "Studio")
        entries = _inventory(root)
        release = {
            "schema": SCHEMA, "kind": KIND, "revision": revision,
            "platform": platform, "game": "Jeanne",
            "studio": "Studio/" + studio_exe.name,
            "r15_manifest_sha256": _digest(game / "manifest.json"),
            "signature": "not-asserted", "certification": "preview-NO-GO",
            "license_warnings": game_manifest.get("license_warnings", []),
            "files": entries,
        }
        (root / "release.json").write_text(
            json.dumps(release, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        verify_portable(root, revision=revision, platform=platform)
        with destination.open("xb") as stream:
            if platform == "Windows":
                with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED,
                                     compresslevel=8) as output:
                    for node in _tree_files(root):
                        rel = "DrawTemp/" + node.relative_to(root).as_posix()
                        info = zipfile.ZipInfo(rel, (1980, 1, 1, 0, 0, 0))
                        info.compress_type = zipfile.ZIP_DEFLATED
                        info.external_attr = (stat.S_IMODE(node.stat().st_mode) & 0o777) << 16
                        output.writestr(info, node.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
            else:
                with gzip.GzipFile(filename="", mode="wb", fileobj=stream,
                                   mtime=0) as gz:
                    with tarfile.open(fileobj=gz, mode="w") as tar:
                        for node in _tree_files(root):
                            rel = "DrawTemp/" + node.relative_to(root).as_posix()
                            info = tarfile.TarInfo(rel)
                            info.size = node.stat().st_size
                            info.mode = stat.S_IMODE(node.stat().st_mode) & 0o777
                            info.uid = info.gid = 0
                            info.mtime = 0
                            with node.open("rb") as source:
                                tar.addfile(info, source)
    sidecar = destination.with_name(destination.name + ".sha256")
    if sidecar.exists() or sidecar.is_symlink():
        destination.unlink()
        raise ReleaseError("Digest sidecar already exists")
    sidecar.write_text(_digest(destination) + "  " + destination.name + "\n",
                       encoding="ascii")
    return {"archive": str(destination), "sha256": _digest(destination),
            "sidecar": str(sidecar), "revision": revision, "platform": platform,
            "certification": "preview-NO-GO"}


def _stream_file(source, target, expected):
    written = 0
    h = sha256()
    with target.open("xb") as output:
        while True:
            block = source.read(min(1024 * 1024, expected - written))
            if not block:
                break
            output.write(block)
            h.update(block)
            written += len(block)
            if written > expected:
                raise ReleaseError("Archive member exceeds declared size")
    if written != expected:
        raise ReleaseError("Archive member is truncated")
    return h.hexdigest()


def install_preview(archive, destination, *, expected_sha256, revision=None, platform=None):
    """Bounded extraction with atomic install; existing installs stay untouched.

    The caller supplies a SHA-256 from an independently obtained source.
    The SHA proves byte equality, NOT producer authenticity/signing.
    """
    archive = Path(archive).resolve(strict=True)
    if not isinstance(expected_sha256, str) or not SHA64.fullmatch(expected_sha256):
        raise ReleaseError("Expected SHA-256 must be provided")
    if _digest(archive) != expected_sha256:
        raise ReleaseError("Archive SHA-256 mismatch")
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ReleaseError("Install destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    zip_format = zipfile.is_zipfile(archive)
    with TemporaryDirectory(prefix=".r23c-install-", dir=destination.parent) as work:
        stage = Path(work) / "DrawTemp"
        stage.mkdir()
        seen = set()
        count = 0
        total = 0

        def checked(name, size):
            nonlocal count, total
            name = _relative(name)
            if not name.startswith("DrawTemp/"):
                raise ReleaseError("Archive entry is outside the application")
            rel = _relative(name[len("DrawTemp/"):])
            if rel.casefold() in seen:
                raise ReleaseError("Duplicate archive member")
            seen.add(rel.casefold())
            if type(size) is not int or not 0 <= size <= MAX_MEMBER_BYTES:
                raise ReleaseError("Oversized archive member")
            count += 1
            total += size
            if count > MAX_FILES or total > MAX_TOTAL_BYTES:
                raise ReleaseError("Archive exceeds extraction limits")
            result = stage.joinpath(*rel.split("/"))
            result.parent.mkdir(parents=True, exist_ok=True)
            return result

        if zip_format:
            with zipfile.ZipFile(archive) as content:
                for item in content.infolist():
                    if item.is_dir():
                        raise ReleaseError("Unexpected archive directory entry")
                    unix_mode = item.external_attr >> 16
                    if stat.S_IFMT(unix_mode) not in (0, stat.S_IFREG):
                        raise ReleaseError("Archive link or special file forbidden")
                    target = checked(item.filename, item.file_size)
                    with content.open(item, "r") as stream:
                        _stream_file(stream, target, item.file_size)
                    if os.name != "nt":
                        target.chmod(unix_mode & 0o777 or 0o644)
        else:
            with tarfile.open(archive, "r:gz") as content:
                for item in content:
                    if not item.isfile():
                        raise ReleaseError("Archive link or special file forbidden")
                    target = checked(item.name, item.size)
                    with content.extractfile(item) as stream:
                        _stream_file(stream, target, item.size)
                    target.chmod(item.mode & 0o777)
        verify_portable(stage, revision=revision, platform=platform)
        os.replace(stage, destination)
    return destination


def remove_preview(destination):
    """Explicit local uninstallation; never remove symlink or unknown directory."""
    destination = Path(destination).absolute()
    if destination.is_symlink() or not destination.is_dir():
        raise ReleaseError("Not an installed portable preview")
    verify_portable(destination)
    shutil.rmtree(destination)
    return destination
