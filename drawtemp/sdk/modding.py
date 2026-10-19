"""R47.A: fail-closed declarative mod contracts (no third-party code execution).

This extends R24's controlled extensions and R30's verified resource packs;
resource declarations do not establish copyright clearance or signatures.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from drawtemp.sdk.capability_contracts import CapabilityError, parse_semver, require_sdk
from drawtemp.export.creator_packs import PackError, inspect_pack

SCHEMA = 1
MAX_MANIFEST_BYTES = 65536
MAX_DEPENDENCIES = 32
MAX_RESOURCES = 64
PERMISSIONS = frozenset({"project.read", "project.extensions.write"})
_ID = re.compile(r"[a-z][a-z0-9-]{2,63}\Z")
_NAMESPACE = re.compile(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,5}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_LICENSE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]{1,63}\Z")


class ModError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(detail)


def _fail(code, message):
    raise ModError(code, message)


def _object(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        _fail("invalid_manifest", label + ": unexpected or missing fields")


def _identifier(value, expression, label):
    if type(value) is not str or not expression.fullmatch(value):
        _fail("invalid_manifest", label + ": invalid identifier")


def _version(value):
    try:
        return parse_semver(value)
    except CapabilityError as exc:
        raise ModError("invalid_version", str(exc)) from exc


def _requirements(data):
    _object(data, {"min_api", "max_api", "features"}, "requires")
    features = data["features"]
    if type(features) is not list or "modding-declarative.v1" not in features:
        _fail("invalid_manifest", "modding-declarative.v1 must be declared")
    try:
        require_sdk(min_api=data["min_api"], max_api=data["max_api"],
                    required_features=features)
    except CapabilityError as exc:
        raise ModError("incompatible_sdk", str(exc)) from exc


def _duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_json_key", "Duplicate JSON key: " + key)
        result[key] = value
    return result


def validate_mod_manifest(document):
    """Validate an inert descriptor; returned data is detached from the caller.

    The only possible mutation is an R24 GameProject extension via the host's
    AuthoringSession. No network, filesystem, Python/QML entrypoint or hook API.
    """
    _object(document, {"schema", "id", "version", "namespace", "requires",
                       "permissions", "dependencies", "resources", "extension",
                       "rights"}, "mod")
    if type(document["schema"]) is not int or document["schema"] != SCHEMA:
        _fail("unsupported_schema", "Unsupported mod manifest schema")
    _identifier(document["id"], _ID, "mod")
    _identifier(document["namespace"], _NAMESPACE, "namespace")
    _version(document["version"])
    _requirements(document["requires"])
    permissions = document["permissions"]
    if (type(permissions) is not list or len(permissions) != len(set(map(repr, permissions)))
            or any(type(item) is not str or item not in PERMISSIONS for item in permissions)):
        _fail("invalid_permissions", "Unknown or duplicate permissions")
    extension = document["extension"]
    if extension is not None:
        _object(extension, {"data", "references"}, "extension")
        if type(extension["data"]) is not dict or type(extension["references"]) is not list:
            _fail("invalid_manifest", "Extension requires object data and references")
        if "project.extensions.write" not in permissions:
            _fail("invalid_permissions", "Extension requires project.extensions.write")
    elif "project.extensions.write" in permissions:
        _fail("invalid_permissions", "Write grant without extension is forbidden")
    dependencies = document["dependencies"]
    if type(dependencies) is not list or len(dependencies) > MAX_DEPENDENCIES:
        _fail("invalid_dependencies", "Dependencies must be a bounded list")
    seen = set()
    for dep in dependencies:
        _object(dep, {"id", "min_version", "max_version"}, "dependency")
        _identifier(dep["id"], _ID, "dependency")
        if dep["id"] in seen or dep["id"] == document["id"]:
            _fail("invalid_dependencies", "Duplicate or self-dependency")
        seen.add(dep["id"])
        if _version(dep["min_version"]) >= _version(dep["max_version"]):
            _fail("invalid_dependencies", "Empty dependency version range")
    resources = document["resources"]
    if type(resources) is not list or len(resources) > MAX_RESOURCES:
        _fail("invalid_resources", "Resources must be a bounded list")
    resource_ids = set()
    for row in resources:
        _object(row, {"id", "version", "sha256"}, "resource")
        _identifier(row["id"], _ID, "resource")
        _version(row["version"])
        _identifier(row["sha256"], _SHA, "resource digest")
        if row["id"] in resource_ids:
            _fail("invalid_resources", "Duplicate resource pack")
        resource_ids.add(row["id"])
    rights = document["rights"]
    _object(rights, {"license", "origin", "evidence", "redistributable"}, "rights")
    _identifier(rights["license"], _LICENSE, "license")
    if (any(type(rights[key]) is not str or not rights[key].strip() or
            len(rights[key]) > 500 for key in ("origin", "evidence")) or
            type(rights["redistributable"]) is not bool):
        _fail("invalid_rights", "Explicit origin, evidence and redistribution flag required")
    try:
        encoded = json.dumps(document, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ModError("invalid_manifest", "Manifest is not valid bounded JSON") from exc
    if len(encoded) > MAX_MANIFEST_BYTES:
        _fail("size_limit", "Manifest exceeds 64 KiB")
    return deepcopy(document)


def read_mod_manifest(path):
    """Only a manually chosen regular JSON file, never arbitrary modules."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        _fail("unsafe_path", "Expected a regular, non-symlink manifest")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            _fail("size_limit", "Manifest exceeds 64 KiB")
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_duplicates,
                         parse_constant=lambda value: _fail("invalid_manifest", "Invalid number"))
    except ModError:
        raise
    except (UnicodeError, OSError, ValueError, TypeError) as exc:
        raise ModError("invalid_manifest", "Cannot read manifest") from exc
    return validate_mod_manifest(doc)


class ModRegistry:
    """Ephemeral registry: revocable grants; no implicit imports or auto-loads."""

    def __init__(self):
        self._entries = {}

    def install(self, document, *, resource_paths=None):
        mod = validate_mod_manifest(document)
        mid = mod["id"]
        if mid in self._entries or any(row["manifest"]["namespace"] == mod["namespace"]
                                       for row in self._entries.values()):
            _fail("collision", "Mod id or namespace already installed")
        for dep in mod["dependencies"]:
            installed = self._entries.get(dep["id"])
            if installed is None:
                _fail("missing_dependency", "Required mod not installed: " + dep["id"])
            version = _version(installed["manifest"]["version"])
            if not (_version(dep["min_version"]) <= version < _version(dep["max_version"])):
                _fail("incompatible_dependency", dep["id"] + " version mismatch")
        paths = resource_paths if resource_paths is not None else {}
        if type(paths) is not dict or set(paths) != {r["id"] for r in mod["resources"]}:
            _fail("missing_resource", "Exact pinned resource pack mapping required")
        for res in mod["resources"]:
            path = Path(paths[res["id"]])
            if path.is_symlink() or not path.is_file():
                _fail("unsafe_resource", "Resource pack must be a regular, non-symlink file")
            try:
                report = inspect_pack(path)
            except (PackError, OSError, ValueError, TypeError) as exc:
                raise ModError("invalid_resource", "Resource pack could not be verified") from exc
            if (report.pack_id, report.version, report.archive_sha256) != (
                    res["id"], res["version"], res["sha256"]):
                _fail("resource_mismatch", "Resource pack identity or SHA-256 changed")
        digest = hashlib.sha256(json.dumps(mod, sort_keys=True, separators=(",", ":"),
                                           ensure_ascii=True).encode("utf-8")).hexdigest()
        self._entries[mid] = {"manifest": mod, "digest": digest,
                              "resource_paths": {key: Path(value) for key, value in paths.items()},
                              "enabled": False, "grants": frozenset()}
        return self.status(mid)

    def _entry(self, mod_id):
        if type(mod_id) is not str or mod_id not in self._entries:
            _fail("unknown_mod", "Mod not installed")
        return self._entries[mod_id]

    def manifest(self, mod_id):
        """A detached, inert descriptor for consent screens and inspection."""
        return deepcopy(self._entry(mod_id)["manifest"])

    def statuses(self):
        """Stable snapshot for host-managed plugin inspectors."""
        return tuple(self.status(mod_id) for mod_id in sorted(self._entries))

    def status(self, mod_id):
        entry = self._entry(mod_id)
        doc = entry["manifest"]
        return {"id": doc["id"], "version": doc["version"],
                "namespace": doc["namespace"], "manifest_sha256": entry["digest"],
                "required_permissions": list(doc["permissions"]),
                "grants": sorted(entry["grants"]), "enabled": entry["enabled"],
                "rights_verified": False, "code_executed": False}

    def enable(self, mod_id, *, grants):
        entry = self._entry(mod_id)
        declared = frozenset(entry["manifest"]["permissions"])
        if (type(grants) not in (list, tuple, set, frozenset) or
                any(type(item) is not str for item in grants) or
                len(grants) != len(set(grants)) or frozenset(grants) != declared):
            _fail("permission_denied", "Explicit exact grants are required")
        entry["grants"], entry["enabled"] = declared, True
        return self.status(mod_id)

    def disable(self, mod_id):
        entry = self._entry(mod_id)
        entry["enabled"], entry["grants"] = False, frozenset()
        return self.status(mod_id)

    def preview_extension(self, mod_id, editor):
        entry = self._entry(mod_id)
        if not entry["enabled"] or "project.extensions.write" not in entry["grants"]:
            _fail("permission_denied", "Mod has no active write grant")
        mod = entry["manifest"]
        if mod["extension"] is None:
            _fail("no_contribution", "Mod does not declare an extension")
        namespace = mod["namespace"]
        envelope = {"schema_version": 1, **deepcopy(mod["extension"])}

        def transform(project):
            extensions = project.setdefault("extensions", {})
            if namespace in extensions:
                _fail("already_exists", "Namespace is already populated")
            extensions[namespace] = deepcopy(envelope)
            return project

        return editor.preview_project(transform, kind="r47.mod." + mod_id)

    def apply_extension(self, mod_id, editor, *, expected_revision):
        if type(expected_revision) is not int or editor.revision != expected_revision:
            _fail("stale_revision", "Refresh the Studio document before applying")
        plan = self.preview_extension(mod_id, editor)
        return editor.apply(plan)

    def audit_project(self, project, *, expected_pins):
        """R47.C: read-only fail-closed mod inventory for a canonical project.

        Caller supplies IDs and pinned manifest SHA-256 values from a
        separately trusted inventory. This NEVER approves legal rights or a
        standalone Player build. A missing mod is a diagnostic, never deleted
        project data. Resources are rehashed, not trusted from install time.
        """
        if (type(expected_pins) is not dict or len(expected_pins) > 32 or
                any(type(mid) is not str or not _ID.fullmatch(mid) or
                    type(digest) is not str or not _SHA.fullmatch(digest)
                    for mid, digest in expected_pins.items())):
            _fail("invalid_pins", "Expected a bounded mapping of mod IDs to SHA-256")
        if hasattr(project, "to_dict"):
            project = project.to_dict()
        if type(project) is dict and "project" in project:
            project = project["project"]
        if (type(project) is not dict or type(project.get("version")) is not int or
                project["version"] != 1 or type(project.get("campaigns")) is not list or
                type(project.get("extensions", {})) is not dict):
            _fail("invalid_project", "Expected canonical GameProject v1 structure")
        # GameProject.to_dict() omits an empty extensions mapping by design.
        namespaces = project.get("extensions", {})
        errors, verified = [], []
        for mod_id, expected_sha in sorted(expected_pins.items()):
            entry = self._entries.get(mod_id)
            if entry is None:
                errors.append(mod_id + ": missing_mod")
                continue
            doc = entry["manifest"]
            if entry["digest"] != expected_sha:
                errors.append(mod_id + ": manifest_changed")
                continue
            try:
                validate_mod_manifest(doc)
            except ModError:
                errors.append(mod_id + ": incompatible_manifest")
                continue
            if doc["extension"] is not None and doc["namespace"] not in namespaces:
                errors.append(mod_id + ": missing_namespace")
                continue
            if doc["extension"] is not None:
                namespace_data = namespaces[doc["namespace"]]
                expected_data = {"schema_version": 1, **doc["extension"]}
                if type(namespace_data) is not dict:
                    errors.append(mod_id + ": invalid_namespace")
                    continue
                # R47.A allows only an initial immutable declarative insert.
                # A future mutable mod schema will require an explicit
                # versioned migration instead of silently trusting edits.
                if namespace_data != expected_data:
                    errors.append(mod_id + ": namespace_changed")
                    continue
            damaged = False
            for resource in doc["resources"]:
                path = entry["resource_paths"].get(resource["id"])
                try:
                    if path is None or path.is_symlink() or not path.is_file():
                        raise ValueError("Resource no longer exists")
                    current = inspect_pack(path)
                    if (current.pack_id, current.version, current.archive_sha256) != (
                            resource["id"], resource["version"], resource["sha256"]):
                        raise ValueError("Resource digest changed")
                except (PackError, OSError, ValueError, TypeError):
                    errors.append(mod_id + ": resource_changed")
                    damaged = True
                    break
            if damaged:
                continue
            verified.append(mod_id)
        return {"compatible": not errors, "errors": errors,
                "verified_mod_ids": verified, "rights_verified": False,
                "native_export_verified": False, "release_certified": False}

    def replace_version(self, mod_id, document, *, project,
                        resource_paths=None, allow_downgrade=False):
        """Atomically replace ONLY inert mod metadata; never migrate project data.

        This deliberately cannot upgrade a schema, namespace or contribution
        payload. Such changes need a separate validated AuthoringSession
        migration. Every replacement revokes prior grants, including when
        the requested permissions are unchanged.
        """
        old = self._entry(mod_id)
        replacement = validate_mod_manifest(document)
        previous = old["manifest"]
        if replacement["id"] != mod_id or replacement["namespace"] != previous["namespace"]:
            _fail("identity_changed", "A version replacement cannot change mod identity")
        if replacement["extension"] != previous["extension"]:
            _fail("migration_required", "Project data migration must be explicit")
        current_version = _version(previous["version"])
        target_version = _version(replacement["version"])
        if target_version == current_version:
            _fail("same_version", "Publish a new SemVer to change a manifest")
        if type(allow_downgrade) is not bool:
            _fail("invalid_downgrade", "Expected an explicit downgrade decision")
        downgrading = target_version < current_version
        if downgrading and not allow_downgrade:
            _fail("downgrade_denied", "Downgrade needs explicit approval")

        if hasattr(project, "to_dict"):
            project = project.to_dict()
        if type(project) is dict and "project" in project:
            project = project["project"]
        if (type(project) is not dict or type(project.get("version")) is not int or
                project["version"] != 1 or type(project.get("campaigns")) is not list or
                type(project.get("extensions", {})) is not dict):
            _fail("invalid_project", "Expected canonical GameProject v1 structure")
        data = project.get("extensions", {}).get(previous["namespace"])
        if data is not None and data != {
                "schema_version": 1, **(previous["extension"] or {})}:
            _fail("data_in_use", "Existing namespace differs from pinned declaration")
        if data is not None and previous["extension"] is None:
            _fail("data_in_use", "Unknown extension data must be kept untouched")

        # Validate dependants before modifying even a temporary registry.
        for dependent_id, dependent in self._entries.items():
            if dependent_id == mod_id:
                continue
            for need in dependent["manifest"]["dependencies"]:
                if (need["id"] == mod_id and not (
                        _version(need["min_version"]) <= target_version <
                        _version(need["max_version"]))):
                    _fail("incompatible_dependent",
                          dependent_id + " requires the installed version")

        paths = (old["resource_paths"] if resource_paths is None else resource_paths)
        # Install a fully validated replacement in a detached registry first:
        # SDK/rights syntax, outgoing dependencies, ZIP hashes, ID collisions.
        staged = ModRegistry()
        staged._entries = {key: entry for key, entry in self._entries.items()
                           if key != mod_id}
        status = staged.install(replacement, resource_paths=paths)
        # The original registry and all its grants are unchanged on failure.
        self._entries[mod_id] = staged._entries[mod_id]
        return {"id": mod_id, "previous_version": previous["version"],
                "version": status["version"], "downgraded": downgrading,
                "grants_revoked": True, "project_modified": False,
                "rights_verified": False}

    def uninstall(self, mod_id, *, project):
        """Unregister metadata only; never delete user data or asset files."""
        entry = self._entry(mod_id)
        for other_id, other in self._entries.items():
            if other_id != mod_id and any(dep["id"] == mod_id
                    for dep in other["manifest"]["dependencies"]):
                _fail("dependency_in_use", "Dependent mod must be removed first")
        if hasattr(project, "to_dict"):
            project = project.to_dict()
        if type(project) is not dict:
            _fail("invalid_project", "Project snapshot required to prevent data loss")
        if "project" in project:
            project = project["project"]
        if (type(project) is not dict or type(project.get("version")) is not int or
                project["version"] != 1 or type(project.get("campaigns")) is not list or
                type(project.get("extensions", {})) is not dict):
            _fail("invalid_project", "Expected canonical GameProject v1 structure")
        if entry["manifest"]["namespace"] in project.get("extensions", {}):
            _fail("data_in_use", "Existing extension data must remain accessible")
        self.disable(mod_id)
        del self._entries[mod_id]
        return {"removed": mod_id, "deleted_project_data": False,
                "deleted_asset_files": False}
