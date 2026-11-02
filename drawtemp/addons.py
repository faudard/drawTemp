"""Headless Unified Add-on Foundation (schema v3).

Legacy formats are inventoried through their existing validators, never executed,
migrated or granted new rights. This is metadata only: UI/game hooks follow later.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

from drawtemp.sdk.capability_contracts import CapabilityError, parse_semver, require_sdk

SCHEMA_VERSION = 3
MAX_MANIFEST_BYTES = 64 * 1024
MAX_DEPENDENCIES = 32
MAX_CONTRIBUTIONS = 64
_ID = re.compile(r"[a-z][a-z0-9-]{2,63}\Z")
_NAMESPACE = re.compile(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,7}\Z")
_COMPONENT = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_LICENSE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]{1,63}\Z")

POINT_PERMISSIONS = {
    "studio.dock": frozenset({"project.read"}),
    "studio.tool": frozenset({"project.read", "map.tiles.write"}),
    "studio.menu": frozenset({"project.read"}),
    "game.event": frozenset({"events.write"}),
    "assets.pack": frozenset({"assets.read"}),
    "project.template": frozenset({"project.extensions.write"}),
}
KIND_POINTS = {
    "editor": frozenset({"studio.dock", "studio.tool", "studio.menu"}),
    "game": frozenset({"game.event"}),
    "assets": frozenset({"assets.pack"}),
    "template": frozenset({"project.template"}),
    "hybrid": frozenset(POINT_PERMISSIONS),
}
# Reject executable declarations, including those nested in JSON config.
_FORBIDDEN_CONFIG = frozenset({
    "entrypoint", "python", "module", "script", "exec", "eval",
    "subprocess", "qml", "executable", "import",
})


class AddonError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise AddonError(code, message)


def _fields(obj, expected, context):
    if type(obj) is not dict or set(obj) != set(expected):
        _fail("invalid_manifest", context + ": unexpected or missing fields")


def _id(value, regex, label):
    if type(value) is not str or not regex.fullmatch(value):
        _fail("invalid_manifest", label + ": invalid identifier")


def _text(value, label, limit=256):
    if type(value) is not str or not value.strip() or len(value) > limit:
        _fail("invalid_manifest", label + ": invalid text")


def _version(value):
    try:
        return parse_semver(value)
    except CapabilityError as exc:
        raise AddonError("invalid_version", str(exc)) from exc


def _unique(value, label):
    if type(value) is not list or any(type(item) is not str for item in value):
        _fail("invalid_manifest", label + ": expected a string list")
    if len(value) != len(set(value)):
        _fail("invalid_manifest", label + ": duplicate values")
    return value


def _inert_json(value, depth=0):
    if depth > 16:
        _fail("invalid_config", "JSON nesting too deep")
    if value is None or type(value) in (str, int, bool):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _inert_json(item, depth + 1)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str or key.lower() in _FORBIDDEN_CONFIG:
                _fail("executable_config", "Executable config fields are unsupported")
            _inert_json(item, depth + 1)
        return
    _fail("invalid_config", "Only finite JSON values are supported")


def _encoded(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise AddonError("invalid_manifest", "Invalid JSON encoding") from exc
    if len(raw) > MAX_MANIFEST_BYTES:
        _fail("size_limit", "Manifest exceeds 64 KiB")
    return raw


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            _fail("duplicate_json_key", "Duplicate JSON key: " + key)
        value[key] = item
    return value


def _invalid_number(value):
    _fail("invalid_manifest", "Non-JSON number: " + value)


def read_addon_manifest(path):
    """Read a manually selected regular JSON file, never a symlink/module."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        _fail("unsafe_path", "Expected a regular non-symlink file")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            _fail("size_limit", "Manifest exceeds 64 KiB")
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                          parse_constant=_invalid_number)
    except AddonError:
        raise
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise AddonError("invalid_manifest", "Cannot decode add-on JSON") from exc


def validate_addon_manifest(obj):
    """Validate *inert* v3 descriptors; does not authorize code or write data."""
    _fields(obj, {
        "schema_version", "id", "name", "namespace", "version", "kind",
        "sdk", "capabilities", "permissions", "dependencies",
        "contributions", "rights",
    }, "addon")
    if type(obj["schema_version"]) is not int or obj["schema_version"] != SCHEMA_VERSION:
        _fail("unsupported_schema", "Expected schema_version 3")
    _id(obj["id"], _ID, "id")
    _id(obj["namespace"], _NAMESPACE, "namespace")
    _text(obj["name"], "name", 100)
    _version(obj["version"])
    kind = obj["kind"]
    if type(kind) is not str or kind not in KIND_POINTS:
        _fail("invalid_manifest", "Unknown add-on kind")
    sdk = obj["sdk"]
    _fields(sdk, {"min_api", "max_api", "required_features"}, "sdk")
    features = _unique(sdk["required_features"], "sdk.required_features")
    if "addons-foundation.v1" not in features:
        _fail("invalid_manifest", "Missing required addons-foundation.v1 feature")
    try:
        require_sdk(min_api=sdk["min_api"], max_api=sdk["max_api"],
                    required_features=features)
    except CapabilityError as exc:
        raise AddonError("incompatible_sdk", str(exc)) from exc
    capabilities = _unique(obj["capabilities"], "capabilities")
    if not capabilities or any(point not in KIND_POINTS[kind] for point in capabilities):
        _fail("invalid_capability", "Unknown or incompatible contribution point")
    permissions = _unique(obj["permissions"], "permissions")
    contributions = obj["contributions"]
    if type(contributions) is not list or not 1 <= len(contributions) <= MAX_CONTRIBUTIONS:
        _fail("invalid_manifest", "Expected 1..64 contributions")
    identifiers, used = set(), set()
    for contribution in contributions:
        _fields(contribution, {"id", "point", "config"}, "contribution")
        _id(contribution["id"], _COMPONENT, "contribution.id")
        point = contribution["point"]
        if type(point) is not str or point not in capabilities:
            _fail("invalid_capability", "Contribution point was not declared")
        if contribution["id"] in identifiers:
            _fail("duplicate_contribution", "Duplicate contribution id")
        identifiers.add(contribution["id"])
        used.add(point)
        if type(contribution["config"]) is not dict:
            _fail("invalid_config", "Contribution config must be a JSON object")
        _inert_json(contribution["config"])
    if used != set(capabilities):
        _fail("invalid_capability", "Capabilities must match contributions")
    required = set().union(*(POINT_PERMISSIONS[point] for point in used))
    if set(permissions) != required:
        _fail("invalid_permission", "Permissions must exactly match contributions")
    dependencies = obj["dependencies"]
    if type(dependencies) is not list or len(dependencies) > MAX_DEPENDENCIES:
        _fail("invalid_dependency", "Expected at most 32 dependencies")
    seen = set()
    for dep in dependencies:
        _fields(dep, {"id", "min_version", "max_version"}, "dependency")
        _id(dep["id"], _ID, "dependency.id")
        if dep["id"] == obj["id"] or dep["id"] in seen:
            _fail("invalid_dependency", "Self/duplicate dependency")
        seen.add(dep["id"])
        if _version(dep["min_version"]) >= _version(dep["max_version"]):
            _fail("invalid_dependency", "Empty version interval")
    rights = obj["rights"]
    _fields(rights, {"license", "origin", "redistributable"}, "rights")
    _id(rights["license"], _LICENSE, "license")
    _text(rights["origin"], "origin", 500)
    if type(rights["redistributable"]) is not bool:
        _fail("invalid_manifest", "redistributable must be a boolean")
    _encoded(obj)
    return deepcopy(obj)


def _classify(document):
    if type(document) is not dict:
        _fail("invalid_manifest", "Expected a JSON object")
    if "schema_version" in document:
        return "addon-v3", validate_addon_manifest(document)
    if "api_version" in document:
        try:
            if type(document["api_version"]) is int and document["api_version"] == 1:
                from drawtemp.export.extensions import validate_extension_manifest
                return "r15-v1", validate_extension_manifest(document)
            if type(document["api_version"]) is int and document["api_version"] == 2:
                from drawtemp.studio.plugins import validate_studio_manifest
                return "r24-v2", validate_studio_manifest(document)
        except (ValueError, TypeError) as exc:
            raise AddonError("invalid_legacy_manifest", str(exc)) from exc
    if document.get("schema") == 1:
        try:
            from drawtemp.sdk.modding import validate_mod_manifest
            return "r47-mod-v1", validate_mod_manifest(document)
        except (ValueError, TypeError) as exc:
            raise AddonError("invalid_legacy_manifest", str(exc)) from exc
    _fail("unsupported_schema", "Unrecognised manifest format")


class AddonManager:
    """Unified metadata registry. Does not execute or activate contributions."""

    def __init__(self):
        self._records = {}

    def register(self, manifest):
        """Register v3 or inventory legacy. Legacy permissions stay unusable."""
        family, document = _classify(manifest)
        addon_id, namespace = document["id"], document.get("namespace")
        if addon_id in self._records or (
            namespace is not None and any(
                record["manifest"].get("namespace") == namespace
                for record in self._records.values()
            )
        ):
            _fail("collision", "Duplicate id or namespace")
        if family == "addon-v3":
            for dep in document["dependencies"]:
                upstream = self._records.get(dep["id"])
                if upstream is None:
                    _fail("missing_dependency", "Missing dependency: " + dep["id"])
                if upstream["family"] != "addon-v3":
                    _fail("legacy_dependency", "Cannot depend on a legacy manifest")
                version = _version(upstream["manifest"]["version"])
                if not (_version(dep["min_version"]) <= version < _version(dep["max_version"])):
                    _fail("incompatible_dependency", "Out-of-range dependency: " + dep["id"])
        self._records[addon_id] = {
            "family": family, "manifest": deepcopy(document),
            "sha256": hashlib.sha256(_encoded(document)).hexdigest(),
            "enabled": False, "grants": frozenset(),
        }
        return self.status(addon_id)

    def register_file(self, path):
        return self.register(read_addon_manifest(path))

    def _get(self, addon_id):
        if type(addon_id) is not str or addon_id not in self._records:
            _fail("unknown_addon", "Add-on not registered")
        return self._records[addon_id]

    def manifest(self, addon_id):
        return deepcopy(self._get(addon_id)["manifest"])

    def status(self, addon_id):
        record = self._get(addon_id)
        manifest = record["manifest"]
        return {
            "id": addon_id,
            "name": manifest.get("name", addon_id),
            "namespace": manifest.get("namespace"),
            "version": manifest.get("version"),
            "format": record["family"],
            "manifest_sha256": record["sha256"],
            "capabilities": list(manifest.get("capabilities", [])),
            "required_permissions": list(manifest.get("permissions", [])),
            "grants": sorted(record["grants"]),
            "enabled": record["enabled"],
            "legacy_read_only": record["family"] != "addon-v3",
            "code_executed": False,
        }

    def statuses(self):
        return tuple(self.status(addon_id) for addon_id in sorted(self._records))

    def enable(self, addon_id, *, grants):
        """Record consent in memory only. No external code, files or UI."""
        record = self._get(addon_id)
        if record["family"] != "addon-v3":
            _fail("legacy_read_only", "Use the original R15/R24/R47 API")
        if type(grants) not in (list, tuple, set, frozenset) or any(
            type(p) is not str for p in grants
        ):
            _fail("invalid_permission", "Explicit permission collection required")
        declared = record["manifest"]["permissions"]
        if len(grants) != len(set(grants)) or set(grants) != set(declared):
            _fail("permission_denied", "Exact declared permissions required")
        for dep in record["manifest"]["dependencies"]:
            if not self._get(dep["id"])["enabled"]:
                _fail("dependency_disabled", "Dependency disabled: " + dep["id"])
        record["enabled"] = True
        record["grants"] = frozenset(grants)
        return self.status(addon_id)

    def disable(self, addon_id):
        record = self._get(addon_id)
        for other_id, other in self._records.items():
            if other["enabled"] and any(
                dep["id"] == addon_id for dep in other["manifest"].get("dependencies", [])
            ):
                _fail("required_by", "Still required by enabled add-on: " + other_id)
        record["enabled"] = False
        record["grants"] = frozenset()
        return self.status(addon_id)

    def unregister(self, addon_id):
        self._get(addon_id)
        for other_id, other in self._records.items():
            if other_id != addon_id and any(
                dep["id"] == addon_id for dep in other["manifest"].get("dependencies", [])
            ):
                _fail("required_by", "Still required by: " + other_id)
        del self._records[addon_id]

    def lock(self):
        """Deterministic SHA pins; not a signature or a permission receipt."""
        return {"schema_version": 1, "addons": [
            {"id": state["id"], "format": state["format"],
             "version": state["version"], "manifest_sha256": state["manifest_sha256"]}
            for state in self.statuses()
        ]}

    def verify_lock(self, expected):
        if type(expected) is not dict or expected != self.lock():
            _fail("lock_mismatch", "Registered add-ons differ from lock")
        return True
