"""R24.C — inspectable, deterministic resource packs for canonical GameProject v1.

Packs contain only declarative AssetRegistry entries and their binary assets.
No plugins, Python code, hooks, scripts or alternative registry are loaded.
An import is an explicit AuthoringSession transaction. Failures do not rewrite
existing assets or documents. Cryptographic hashes establish integrity, NOT
authenticity or copyright permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
from zipfile import BadZipFile, ZipFile, ZipInfo, ZIP_STORED
from tempfile import NamedTemporaryFile

from drawtemp.sdk.simulation import freeze, thaw
from sporebound.assets import AssetRegistry

RECEIPT_NAMESPACE = "org.drawtemp.resourcepacks"
PACK_SCHEMA = 1
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 256 * 1024
MAX_FILES = 128
MAX_ENTRIES = 512
MAX_TOTAL_BYTES = 64 * 1024 * 1024
_PACK_ID = re.compile(r"[a-z][a-z0-9-]{2,47}\Z")
_SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_BAD_WINDOWS = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10)
}


class ResourcePackError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def fail(code, message):
    raise ResourcePackError(code, message)


def _exact(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        fail("invalid_manifest", label + ": unexpected or missing fields")


def _id(value):
    if type(value) is not str or not _PACK_ID.fullmatch(value):
        fail("invalid_manifest", "Pack ID must be a portable slug")


def _version(value):
    if type(value) is not str or not _SEMVER.fullmatch(value):
        fail("unsupported_version", "Pack version must be major.minor.patch")


def _hash(value):
    if type(value) is not str or not _HASH.fullmatch(value):
        fail("invalid_manifest", "Expected lowercase SHA-256 hex")


def _path(relative):
    if (type(relative) is not str or not 1 <= len(relative) <= 220 or
            "\\" in relative or relative.startswith("/") or PureWindowsPath(relative).drive):
        fail("unsafe_path", "Pack path must be relative and portable")
    for part in relative.split("/"):
        if (part in ("", ".", "..") or part.endswith((" ", ".")) or
                any(ord(char) < 32 or char in '<>:"|?*' for char in part) or
                part.split(".", 1)[0].upper() in _BAD_WINDOWS):
            fail("unsafe_path", "Non-portable pack path: " + relative)
    return relative


def _no_dupes(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail("invalid_manifest", "Duplicate JSON key " + key)
        result[key] = value
    return result


def _read_archive(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ARCHIVE_BYTES:
        fail("invalid_archive", "Expected a regular, bounded, non-symlink archive")
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_ARCHIVE_BYTES:
            fail("size_limit", "Archive exceeds size limit")
        return raw
    except OSError as exc:
        raise ResourcePackError("invalid_archive", str(exc)) from exc


def _manifest(raw):
    if len(raw) > MAX_MANIFEST_BYTES:
        fail("size_limit", "Pack manifest too large")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dupes)
    except ResourcePackError:
        raise
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ResourcePackError("invalid_manifest", "Invalid pack JSON") from exc


def validate_pack_manifest(document):
    """Strict declarative manifest. Does NOT certify asserted license rights."""
    _exact(document, {"schema_version", "id", "version", "name",
                      "files", "entries", "dependencies"}, "pack")
    if type(document["schema_version"]) is not int or document["schema_version"] != PACK_SCHEMA:
        fail("unsupported_schema", "Pack schema needs an explicit migration")
    _id(document["id"])
    _version(document["version"])
    if (type(document["name"]) is not str or
            not 1 <= len(document["name"].strip()) <= 120):
        fail("invalid_manifest", "Invalid pack display name")
    files, entries, deps = document["files"], document["entries"], document["dependencies"]
    if type(files) is not list or not 1 <= len(files) <= MAX_FILES:
        fail("invalid_manifest", "Pack requires 1..128 binary files")
    if type(entries) is not list or not 1 <= len(entries) <= MAX_ENTRIES:
        fail("invalid_manifest", "Pack requires 1..512 registry entries")
    if type(deps) is not list or len(deps) > 32:
        fail("invalid_manifest", "Too many pack dependencies")
    total, paths, case_paths = 0, set(), set()
    for file in files:
        _exact(file, {"path", "sha256", "bytes", "license"}, "file")
        path = _path(file["path"])
        if path in paths or path.casefold() in case_paths:
            fail("path_collision", "Duplicate/case-colliding pack path: " + path)
        paths.add(path)
        case_paths.add(path.casefold())
        _hash(file["sha256"])
        if type(file["bytes"]) is not int or not 0 < file["bytes"] <= MAX_FILE_BYTES:
            fail("size_limit", "Invalid pack file size")
        total += file["bytes"]
        license = file["license"]
        _exact(license, {"id", "rights_holder", "evidence", "redistributable",
                         "modifiable"}, "license")
        for field in ("id", "rights_holder", "evidence"):
            if (type(license[field]) is not str or
                    not 1 <= len(license[field].strip()) <= 512):
                fail("license_missing", "Missing explicit " + field + " license metadata")
        if type(license["redistributable"]) is not bool or not license["redistributable"]:
            fail("license_unapproved", "Redistribution is not declared as permitted")
        if type(license["modifiable"]) is not bool:
            fail("license_missing", "Modification permission must be explicit")
    if total > MAX_TOTAL_BYTES:
        fail("size_limit", "Pack unpacked size exceeds limit")
    dependency_ids = set()
    for dep in deps:
        _exact(dep, {"id", "version", "sha256"}, "dependency")
        _id(dep["id"])
        _version(dep["version"])
        _hash(dep["sha256"])
        if dep["id"] == document["id"] or dep["id"] in dependency_ids:
            fail("invalid_dependency", "Self/duplicate dependencies are forbidden")
        dependency_ids.add(dep["id"])
    # A standalone AssetRegistry is the sole authority for entry semantics,
    # IDs, animation references and supported extensions.
    ids = set()
    qualified = []
    for entry in entries:
        if type(entry) is not dict or type(entry.get("id")) is not str:
            fail("invalid_manifest", "Malformed asset entry")
        if entry["id"].casefold() in ids:
            fail("id_collision", "Duplicate casefolded asset ID")
        ids.add(entry["id"].casefold())
        item = deepcopy(entry)
        item["id"] = document["id"] + "." + entry["id"]
        if item.get("kind") == "animation":
            if type(item.get("frames")) is list:
                for frame in item["frames"]:
                    if type(frame) is dict and type(frame.get("sprite")) is str:
                        frame["sprite"] = document["id"] + "." + frame["sprite"]
        else:
            if type(item.get("path")) is str:
                if item["path"] not in paths:
                    fail("invalid_manifest", "Registry asset file not included in pack")
                item["path"] = ("assets/packs/" + document["id"] + "/" +
                                document["version"] + "/" + item["path"])
        qualified.append(item)
    try:
        registry = AssetRegistry({"version": 1, "entries": qualified, "bindings": {}})
    except (ValueError, KeyError, TypeError) as exc:
        raise ResourcePackError("invalid_registry", str(exc)) from exc
    referenced = {entry["path"].split("/", 4)[-1]
                  for entry in registry.to_dict()["entries"] if entry["kind"] != "animation"}
    if referenced != paths:
        fail("invalid_manifest", "Pack has unreferenced/unlisted binary files")
    return deepcopy(document)


@dataclass(frozen=True)
class PackPreview:
    path: Path
    sha256: str
    manifest: object

    def to_dict(self):
        return {"archive": str(self.path), "sha256": self.sha256,
                "manifest": thaw(self.manifest)}


def _inspect_raw(raw, path):
    try:
        from io import BytesIO
        with ZipFile(BytesIO(raw)) as archive:
            names = archive.infolist()
            if not 2 <= len(names) <= MAX_FILES + 1:
                fail("invalid_archive", "Unexpected number of archive members")
            paths = set()
            folded = set()
            for item in names:
                name = _path(item.filename)
                if (item.is_dir() or stat.S_ISLNK(item.external_attr >> 16) or
                        name in paths or name.casefold() in folded):
                    fail("unsafe_archive", "Duplicate, directory or symlink entry in pack")
                paths.add(name)
                folded.add(name.casefold())
                if (item.file_size > MAX_FILE_BYTES and name != "pack.json") or (
                        name == "pack.json" and item.file_size > MAX_MANIFEST_BYTES):
                    fail("size_limit", "Oversized archive member")
            if "pack.json" not in paths:
                fail("invalid_archive", "Missing pack.json")
            manifest = validate_pack_manifest(_manifest(archive.read("pack.json")))
            expected = {"pack.json"} | {"files/" + row["path"]
                                        for row in manifest["files"]}
            if paths != expected:
                fail("invalid_archive", "Unexpected/unlisted archive member")
            if sum(info.file_size for info in names) > MAX_TOTAL_BYTES + MAX_MANIFEST_BYTES:
                fail("size_limit", "Uncompressed archive exceeds limit")
            for file in manifest["files"]:
                info = archive.getinfo("files/" + file["path"])
                if info.file_size != file["bytes"]:
                    fail("hash_mismatch", "Size mismatch: " + file["path"])
                digest = sha256()
                size = 0
                with archive.open(info) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                        size += len(chunk)
                        if size > file["bytes"]:
                            fail("size_limit", "Decompression exceeded expected size")
                if size != file["bytes"] or digest.hexdigest() != file["sha256"]:
                    fail("hash_mismatch", "SHA-256 mismatch: " + file["path"])
            return PackPreview(Path(path), sha256(raw).hexdigest(), freeze(manifest))
    except ResourcePackError:
        raise
    except (BadZipFile, OSError, KeyError, ValueError, RuntimeError) as exc:
        raise ResourcePackError("invalid_archive", str(exc)) from exc


def inspect_pack(path):
    """Read and hash all members without changing the project or filesystem."""
    return _inspect_raw(_read_archive(path), path)


def _new_entries(document):
    prefix = "assets/packs/" + document["id"] + "/" + document["version"] + "/"
    entries = deepcopy(document["entries"])
    for row in entries:
        row["id"] = document["id"] + "." + row["id"]
        if row["kind"] == "animation":
            for frame in row["frames"]:
                frame["sprite"] = document["id"] + "." + frame["sprite"]
        else:
            row["path"] = prefix + row["path"]
    return entries


def _receipt(manifest, archive_sha):
    prefix = "assets/packs/" + manifest["id"] + "/" + manifest["version"] + "/"
    return {"id": manifest["id"], "version": manifest["version"],
            "sha256": archive_sha,
            "files": [{"path": prefix + f["path"], "sha256": f["sha256"],
                       "license": deepcopy(f["license"])} for f in manifest["files"]],
            "asset_ids": [manifest["id"] + "." + entry["id"]
                          for entry in manifest["entries"]]}


def _make_transform(manifest, archive_sha):
    def transform(project):
        receipt = _receipt(manifest, archive_sha)
        extensions = project.setdefault("extensions", {})
        stored = extensions.setdefault(RECEIPT_NAMESPACE, {
            "schema_version": 1, "data": {"packs": []}, "references": []})
        if (type(stored) is not dict or stored.get("schema_version") != 1 or
                type(stored.get("data")) is not dict or
                type(stored["data"].get("packs")) is not list):
            fail("invalid_receipts", "Unrecognized pack receipt schema")
        installed = stored["data"]["packs"]
        if any(type(row) is not dict for row in installed):
            fail("invalid_receipts", "Malformed installed pack receipt")
        if any(row.get("id") == manifest["id"] for row in installed):
            fail("already_installed", "Pack ID already installed")
        for dep in manifest["dependencies"]:
            if not any(row.get("id") == dep["id"] and
                       row.get("version") == dep["version"] and
                       row.get("sha256") == dep["sha256"] for row in installed):
                fail("missing_dependency", "Missing pinned pack " + dep["id"])
        data = project.setdefault("assets", {"version": 1, "entries": [],
                                             "bindings": {}})
        if not data:
            data.update({"version": 1, "entries": [], "bindings": {}})
        current = data["entries"]
        candidate = current + _new_entries(manifest)
        try:
            # Explicitly fail on casefold path collisions even when asset IDs differ.
            paths = [row["path"] for row in candidate if row["kind"] != "animation"]
            if len({p.casefold() for p in paths}) < len({p for p in paths}):
                fail("path_collision", "Project has conflicting asset path casings")
            AssetRegistry({**data, "entries": candidate})
        except (ValueError, KeyError, TypeError) as exc:
            raise ResourcePackError("asset_collision", str(exc)) from exc
        data["entries"] = candidate
        installed.append(receipt)
        return project
    return transform


def _safe_destination(root, relative):
    relative = _path(relative)
    root = Path(root).resolve(strict=True)
    result = root / relative
    if not result.resolve(strict=False).is_relative_to(root):
        fail("unsafe_path", "Pack destination escaped project root")
    node = root
    for part in relative.split("/")[:-1]:
        node = node / part
        if node.is_symlink():
            fail("unsafe_path", "Pack destination contains a symlink")
        if node.exists() and not node.is_dir():
            fail("unsafe_path", "Pack parent is not a directory")
    if result.exists() or result.is_symlink():
        fail("already_exists", "Pack file already exists: " + relative)
    return result


def install_pack(preview, editor, project_root, *, expected_revision=None):
    """Verify preview freshness, stage assets, commit ONE authoring history entry.

    A crash while copying may leave orphan files, but cannot silently replace
    existing bytes or mutate project documents. Editor.save remains explicit.
    """
    if not isinstance(preview, PackPreview):
        fail("invalid_preview", "Expected an inspected resource pack")
    root = Path(project_root).resolve(strict=True)
    if not root.is_dir():
        fail("unsafe_path", "Project root must exist")
    if expected_revision is not None and (
            type(expected_revision) is not int or editor.revision != expected_revision):
        fail("stale_revision", "Editor changed since pack inspection")
    raw = _read_archive(preview.path)
    if sha256(raw).hexdigest() != preview.sha256:
        fail("stale_preview", "Pack archive changed after inspection")
    checked = _inspect_raw(raw, preview.path)
    if checked.manifest != preview.manifest:
        fail("stale_preview", "Pack manifest changed")
    manifest = thaw(checked.manifest)
    plan = editor.preview_project(_make_transform(manifest, checked.sha256),
                                  kind="r24.resource-pack")
    if expected_revision is not None and plan.source_revision != expected_revision:
        fail("stale_revision", "Editor changed since pack inspection")
    destinations = []
    for file in manifest["files"]:
        path = ("assets/packs/" + manifest["id"] + "/" + manifest["version"] +
                "/" + file["path"])
        destinations.append((_safe_destination(root, path), file))
    created, created_dirs = [], []
    try:
        from io import BytesIO
        with ZipFile(BytesIO(raw)) as archive:
            for destination, file in destinations:
                parent = destination.parent
                absent = []
                while parent != root and not parent.exists():
                    absent.append(parent)
                    parent = parent.parent
                for folder in reversed(absent):
                    folder.mkdir()  # raises on races, never follows an existing link
                    created_dirs.append(folder)
                _safe_destination(root, destination.relative_to(root).as_posix())
                with destination.open("xb") as out:
                    created.append(destination)
                    with archive.open("files/" + file["path"]) as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            out.write(chunk)
                    out.flush()
                    os.fsync(out.fileno())
                if sha256(destination.read_bytes()).hexdigest() != file["sha256"]:
                    fail("hash_mismatch", "Published bytes changed during installation")
        added = AssetRegistry({"version": 1, "entries": _new_entries(manifest),
                               "bindings": {}})
        problems = added.diagnostics(root)
        if problems:
            fail("invalid_asset", str(problems[0]["message"]))
        return editor.apply(plan)
    except BaseException:
        for destination in reversed(created):
            destination.unlink(missing_ok=True)
        for folder in reversed(created_dirs):
            try:
                folder.rmdir()
            except OSError:
                pass
        raise


def verify_installed_packs(project_root, project):
    """Return all detected receipt/asset digest errors for export preflight.

    This is not a verification of the creator's copyright assertions.
    """
    extensions = project.get("extensions", {})
    if not extensions or RECEIPT_NAMESPACE not in extensions:
        return []
    issues = []
    try:
        receipt = extensions[RECEIPT_NAMESPACE]
        if (type(receipt) is not dict or receipt.get("schema_version") != 1 or
                type(receipt.get("data")) is not dict or
                type(receipt["data"].get("packs")) is not list):
            fail("invalid_receipts", "Invalid pack receipt registry")
        packs = receipt["data"]["packs"]
        assets = AssetRegistry(project.get("assets") or None)
        ids = {row["id"]: row for row in assets.to_dict()["entries"]}
        seen_ids, seen_paths = set(), set()
        for pack in packs:
            _exact(pack, {"id", "version", "sha256", "files", "asset_ids"}, "receipt")
            _id(pack["id"])
            _version(pack["version"])
            _hash(pack["sha256"])
            if pack["id"] in seen_ids:
                fail("invalid_receipts", "Duplicate pack receipt")
            seen_ids.add(pack["id"])
            if type(pack["files"]) is not list or type(pack["asset_ids"]) is not list:
                fail("invalid_receipts", "Invalid pack receipt files/IDs")
            own_ids = set()
            for aid in pack["asset_ids"]:
                if type(aid) is not str or not aid.startswith(pack["id"] + ".") or aid in own_ids or aid not in ids:
                    fail("invalid_receipts", "Missing or duplicate installed asset ID")
                own_ids.add(aid)
            own_paths = set()
            for file in pack["files"]:
                _exact(file, {"path", "sha256", "license"}, "receipt file")
                relative = _path(file["path"])
                prefix = "assets/packs/" + pack["id"] + "/" + pack["version"] + "/"
                if not relative.startswith(prefix) or relative.casefold() in seen_paths:
                    fail("invalid_receipts", "Invalid or repeated installed pack path")
                seen_paths.add(relative.casefold())
                own_paths.add(relative.casefold())
                _hash(file["sha256"])
                license = file["license"]
                _exact(license, {"id", "rights_holder", "evidence",
                                 "redistributable", "modifiable"}, "receipt license")
                if (any(type(license[name]) is not str or not license[name].strip()
                        for name in ("id", "rights_holder", "evidence")) or
                        license["redistributable"] is not True or
                        type(license["modifiable"]) is not bool):
                    fail("invalid_receipts", "Invalid installed license assertion")
                if not any(row.get("path") == relative for row in
                           (ids[aid] for aid in own_ids)):
                    fail("invalid_receipts", "Installed file not referenced by asset registry")
                safe = (Path(project_root).resolve() / relative).resolve()
                if not safe.is_relative_to(Path(project_root).resolve()) or not safe.is_file():
                    issues.append(relative + ": missing/unsafe installed file")
                    continue
                digest = sha256(safe.read_bytes()).hexdigest()
                if digest != file["sha256"]:
                    issues.append(relative + ": installed SHA-256 mismatch")
            for aid in own_ids:
                asset = ids[aid]
                if asset["kind"] != "animation" and asset["path"].casefold() not in own_paths:
                    fail("invalid_receipts", "Untracked asset in installed pack")
    except (ResourcePackError, OSError, ValueError, KeyError, TypeError) as exc:
        issues.append("Resource pack integrity: " + str(exc))
    return issues


def publish_pack(source_root, destination):
    """Create a reproducible ZIP from pack.json + listed files, without overwrite.

    SHA-256 and license assertions must already be present in pack.json.
    Never infers or approves intellectual-property rights automatically.
    """
    root = Path(source_root).resolve(strict=True)
    target = Path(destination)
    if not root.is_dir() or not target.parent.is_dir():
        fail("invalid_path", "Existing source root and output parent required")
    manifest_path = root / "pack.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        fail("invalid_manifest", "Missing regular pack.json")
    manifest = validate_pack_manifest(_manifest(manifest_path.read_bytes()))
    payloads = {}
    size = 0
    for row in manifest["files"]:
        relative = "files/" + row["path"]
        current = root
        for part in relative.split("/"):
            current = current / part
            if current.is_symlink():
                fail("unsafe_path", "Pack input contains a symlink")
        path = root / relative
        if not path.is_file() or not path.resolve().is_relative_to(root):
            fail("unsafe_path", "Pack input is missing or outside source root")
        if path.stat().st_size != row["bytes"]:
            fail("hash_mismatch", "Pack input size differs from manifest")
        payload = path.read_bytes()
        size += len(payload)
        if size > MAX_TOTAL_BYTES or sha256(payload).hexdigest() != row["sha256"]:
            fail("hash_mismatch", "Pack input hash differs from manifest")
        payloads[relative] = payload
    manifest_bytes = json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                                separators=(",", ":")).encode("utf-8")
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        fail("size_limit", "Serialized manifest too large")
    if target.exists() or target.is_symlink():
        fail("already_exists", "Output archive already exists")
    temporary = None
    try:
        with NamedTemporaryFile(mode="w+b", prefix=".drawtemp-pack-", suffix=".tmp",
                                dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            with ZipFile(stream, mode="w", compression=ZIP_STORED) as archive:
                for name, payload in [("pack.json", manifest_bytes)] + sorted(payloads.items()):
                    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_STORED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, payload)
            stream.flush()
            os.fsync(stream.fileno())
        inspect_pack(temporary)
        # Atomic no-overwrite publish. Hardlink failure aborts rather than
        # falling back to a rename that could overwrite another publisher.
        os.link(temporary, target)
        return inspect_pack(target)
    except FileExistsError as exc:
        raise ResourcePackError("already_exists", "Output archive appeared during publication") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
