"""R24.B: non-executable, opt-in Studio plugin contracts and registry.

This intentionally does NOT load third-party Python, QML or subprocesses.
All plugin contributions are host-rendered data and all authored writes use
the existing canonical AuthoringSession. The registry is UI/headless neutral.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re

from drawtemp.sdk.compatibility import SDKCompatibilityError, negotiate_sdk

PLUGIN_MANIFEST_API = 2
CAPABILITIES = frozenset({"property-panel", "project-template"})
PERMISSIONS = frozenset({"project.read", "project.extensions.write"})
PANEL_FIELDS = frozenset({
    "project.title", "project.subtitle", "project.campaign_count",
    "content.mission_count",
})
_ID = re.compile(r"[a-z][a-z0-9-]{2,63}\Z")
_ITEM = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_NAMESPACE = re.compile(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,5}\Z")
_MAX_MANIFEST_BYTES = 65536


class StudioPluginError(ValueError):
    """Stable reason code, safe to surface in the Studio diagnostics dock."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _reject(code, message):
    raise StudioPluginError(code, message)


def _keys(value, keys, context):
    if type(value) is not dict or set(value) != set(keys):
        _reject("invalid_manifest", context + ": unexpected or missing keys")


def _label(value, context, maximum=120):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        _reject("invalid_manifest", context + ": invalid text")


def _ident(value, regex, context):
    if type(value) is not str or not regex.fullmatch(value):
        _reject("invalid_manifest", context + ": invalid id")


def _unique_list(value, allowed, context, *, required=False):
    if type(value) is not list or (required and not value) or any(
            type(item) is not str or item not in allowed for item in value
    ) or len(value) != len(set(value)):
        _reject("invalid_manifest", context + ": invalid or duplicate values")
    return frozenset(value)


def _json_blob(value):
    try:
        encoded = json.dumps(value, ensure_ascii=True, sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) > _MAX_MANIFEST_BYTES:
            _reject("size_limit", "Manifest exceeds 64 KiB")
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise StudioPluginError("invalid_manifest", "Manifest contains invalid JSON") from exc
    return encoded


def validate_studio_manifest(document):
    """Validate strict plugin-v2 metadata without importing plugin code.

    R15's existing v1 asset/plugin descriptor validator remains unchanged.
    An R15 v1 manifest cannot silently gain executable or write privileges.
    """
    if type(document) is not dict:
        _reject("invalid_manifest", "Manifest must be an object")
    if document.get("api_version") != PLUGIN_MANIFEST_API or type(
            document.get("api_version")) is not int:
        _reject("unsupported_api", "R24 Studio needs manifest api_version 2")
    _keys(document, {"api_version", "id", "name", "namespace", "sdk_api",
                     "required_sdk_features", "capabilities", "permissions",
                     "contributions"}, "manifest")
    _ident(document["id"], _ID, "plugin")
    _ident(document["namespace"], _NAMESPACE, "namespace")
    _label(document["name"], "name", 100)
    capabilities = _unique_list(document["capabilities"], CAPABILITIES,
                                "capabilities", required=True)
    declared = _unique_list(document["permissions"], PERMISSIONS, "permissions",
                            required=True)
    required_sdk = _unique_list(
        document["required_sdk_features"],
        frozenset({"sdk-negotiation.v1", "project-extensions.v1"}),
        "required_sdk_features")
    if "sdk-negotiation.v1" not in required_sdk or (
            "project-template" in capabilities and
            "project-extensions.v1" not in required_sdk):
        _reject("invalid_manifest", "Manifest lacks required SDK contracts")
    try:
        negotiate_sdk(document["sdk_api"], required_features=sorted(required_sdk))
    except SDKCompatibilityError as exc:
        raise StudioPluginError("incompatible_sdk", str(exc)) from exc
    sections = document["contributions"]
    _keys(sections, {"panels", "templates"}, "contributions")
    panels, templates = sections["panels"], sections["templates"]
    if type(panels) is not list or len(panels) > 12 or (
            bool(panels) != ("property-panel" in capabilities)):
        _reject("invalid_manifest", "Panel contribution/capability mismatch")
    if type(templates) is not list or len(templates) > 12 or (
            bool(templates) != ("project-template" in capabilities)):
        _reject("invalid_manifest", "Template contribution/capability mismatch")
    expected_permissions = set()
    if panels:
        expected_permissions.add("project.read")
    if templates:
        expected_permissions.add("project.extensions.write")
    if declared != expected_permissions:
        _reject("invalid_permission", "Plugin permissions must match actual contributions")
    panel_ids, template_ids = set(), set()
    for row in panels:
        _keys(row, {"id", "title", "description", "fields"}, "panel")
        _ident(row["id"], _ITEM, "panel")
        _label(row["title"], "panel title")
        if type(row["description"]) is not str or len(row["description"]) > 1000:
            _reject("invalid_manifest", "Invalid panel description")
        fields = _unique_list(row["fields"], PANEL_FIELDS, "panel fields", required=True)
        if row["id"] in panel_ids:
            _reject("duplicate_contribution", "Duplicate panel ID")
        panel_ids.add(row["id"])
    for row in templates:
        _keys(row, {"id", "label", "data", "references"}, "template")
        _ident(row["id"], _ITEM, "template")
        _label(row["label"], "template label")
        if type(row["data"]) is not dict or type(row["references"]) is not list:
            _reject("invalid_manifest", "Template needs a JSON object and reference list")
        if row["id"] in template_ids:
            _reject("duplicate_contribution", "Duplicate template ID")
        template_ids.add(row["id"])
        # The full envelope and its references are validated against actual
        # Content/GameProject by AuthoringSession on apply, never on load.
    _json_blob(document)
    return deepcopy(document)


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _reject("invalid_manifest", "Duplicate JSON property: " + key)
        result[key] = value
    return result


def read_studio_manifest(path):
    """Explicit local-file opt-in; no directory scanning or plugin import."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        _reject("unsafe_path", "Expected a regular, non-symlink JSON manifest")
    try:
        with path.open("rb") as handle:
            raw = handle.read(_MAX_MANIFEST_BYTES + 1)
        if len(raw) > _MAX_MANIFEST_BYTES:
            _reject("size_limit", "Manifest exceeds 64 KiB")
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except StudioPluginError:
        raise
    except (OSError, ValueError, UnicodeError, TypeError) as exc:
        raise StudioPluginError("invalid_manifest", "Cannot read JSON manifest: " + str(exc)) from exc
    return validate_studio_manifest(document)


class StudioPluginRegistry:
    """Opt-in plugin lifecycle with per-plugin isolation and revocable grants."""

    def __init__(self):
        self._plugins = {}

    def install(self, document):
        manifest = validate_studio_manifest(document)
        plugin_id = manifest["id"]
        if plugin_id in self._plugins:
            _reject("duplicate_plugin", "Plugin already installed: " + plugin_id)
        if any(entry["manifest"]["namespace"] == manifest["namespace"]
               for entry in self._plugins.values()):
            _reject("namespace_collision", "Extension namespace already claimed")
        self._plugins[plugin_id] = {
            "manifest": manifest, "grants": frozenset(),
            "enabled": False, "quarantined": False, "error": "",
        }
        return self.status(plugin_id)

    def install_file(self, path):
        return self.install(read_studio_manifest(path))

    def _get(self, plugin_id):
        if type(plugin_id) is not str or plugin_id not in self._plugins:
            _reject("unknown_plugin", "Unknown Studio plugin")
        return self._plugins[plugin_id]

    def status(self, plugin_id):
        entry = self._get(plugin_id)
        return {"id": plugin_id, "name": entry["manifest"]["name"],
                "namespace": entry["manifest"]["namespace"],
                "required_permissions": list(entry["manifest"]["permissions"]),
                "grants": sorted(entry["grants"]),
                "enabled": entry["enabled"], "quarantined": entry["quarantined"],
                "error": entry["error"]}

    def statuses(self):
        return tuple(self.status(pid) for pid in sorted(self._plugins))

    def enable(self, plugin_id, *, grants):
        entry = self._get(plugin_id)
        if entry["quarantined"]:
            _reject("quarantined", "Reinstall the plugin after a runtime failure")
        declared = frozenset(entry["manifest"]["permissions"])
        if type(grants) not in (set, frozenset, tuple, list) or any(
                type(value) is not str for value in grants):
            _reject("invalid_permission", "Permission grants must be explicit strings")
        given = frozenset(grants)
        if len(given) != len(grants) or given != declared:
            _reject("permission_denied", "Enable requires explicit exact permissions")
        entry["grants"] = given
        entry["enabled"] = True
        return self.status(plugin_id)

    def disable(self, plugin_id):
        entry = self._get(plugin_id)
        entry["grants"] = frozenset()
        entry["enabled"] = False
        return self.status(plugin_id)

    def quarantine(self, plugin_id, error):
        """Disable a broken contribution without crashing other plugins."""
        entry = self._get(plugin_id)
        self.disable(plugin_id)
        entry["quarantined"] = True
        entry["error"] = str(error)[:300]
        return self.status(plugin_id)

    def _active(self, plugin_id, permission):
        entry = self._get(plugin_id)
        if not entry["enabled"] or permission not in entry["grants"]:
            _reject("permission_denied", "Plugin is disabled or missing grant " + permission)
        return entry["manifest"]

    def definition(self, plugin_id):
        """Presentation metadata only; does not grant access to project data."""
        return deepcopy(self._get(plugin_id)["manifest"]["contributions"])

    def panel_state(self, plugin_id, panel_id, snapshot):
        """Host resolves whitelisted read-only fields in a detached snapshot."""
        manifest = self._active(plugin_id, "project.read")
        panel = next((row for row in manifest["contributions"]["panels"]
                      if row["id"] == panel_id), None)
        if panel is None:
            _reject("unknown_contribution", "Unknown panel")
        data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else deepcopy(snapshot)
        if type(data) is not dict or type(data.get("project")) is not dict or (
                type(data.get("content")) is not dict):
            _reject("invalid_snapshot", "Expected canonical editor snapshot")
        project, content = data["project"], data["content"]
        values = {
            "project.title": project.get("title", ""),
            "project.subtitle": project.get("subtitle", ""),
            "project.campaign_count": len(project.get("campaigns", [])),
            "content.mission_count": len(content.get("missions", [])),
        }
        return {"id": panel_id, "title": panel["title"],
                "description": panel["description"],
                "fields": tuple((name, values[name]) for name in panel["fields"])}

    def apply_template(self, plugin_id, template_id, editor, *, expected_revision=None):
        """Only permitted write: insert OWN new GameProject extension atomically.

        An existing namespace is NEVER overwritten silently. The existing
        canonical validator checks size/schema/references before the apply.
        """
        manifest = self._active(plugin_id, "project.extensions.write")
        template = next((row for row in manifest["contributions"]["templates"]
                         if row["id"] == template_id), None)
        if template is None:
            _reject("unknown_contribution", "Unknown project template")
        if expected_revision is not None and (
                type(expected_revision) is not int or editor.revision != expected_revision):
            _reject("stale_revision", "Editor changed; refresh before applying template")
        namespace = manifest["namespace"]
        envelope = {"schema_version": 1, "data": deepcopy(template["data"]),
                    "references": deepcopy(template["references"])}

        def transform(project):
            extensions = project.setdefault("extensions", {})
            if namespace in extensions:
                _reject("already_exists", "Plugin extension already exists: " + namespace)
            extensions[namespace] = deepcopy(envelope)
            return project

        # No plugin callback is executed. Bad data or references are rejected
        # atomically by the canonical preview before any history entry.
        plan = editor.preview_project(transform, kind="r24.plugin." + plugin_id)
        return editor.apply(plan)
