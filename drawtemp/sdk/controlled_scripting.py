"""R24.E controlled declarative story-choice hooks, compiled by the Studio.

This is NOT a sandbox or general-purpose Python/Lua scripting interpreter.
Only four native narrative effects may be appended to an existing story choice.
Their execution and replay remain owned by StoryBook/GameSession, not plugins.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.compatibility import negotiate_sdk, SDKCompatibilityError

SCHEMA = 1
MAX_BYTES = 65536
MAX_HOOKS = 16
MAX_EFFECTS = 8
PERMISSION_FOR = {
    "set_flag": "story.flags.write",
    "add_flag": "story.flags.write",
    "unlock_mission": "campaign.missions.unlock",
    "gold": "campaign.gold.write",
}
PERMISSIONS = frozenset(PERMISSION_FOR.values())
_ID = re.compile(r"[a-z][a-z0-9_-]{1,63}\Z")
_NAMESPACE = re.compile(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,5}\Z")


class StudioScriptError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise StudioScriptError(code, message)


def _fields(obj, required, label):
    if type(obj) is not dict or set(obj) != set(required):
        _fail("invalid_script", label + ": unknown or missing fields")


def _identifier(value, label):
    if type(value) is not str or not _ID.fullmatch(value):
        _fail("invalid_script", "Invalid " + label)


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def _scalar(value):
    return type(value) in (str, int, bool) and (
        type(value) is not str or len(value) <= 120) and (
        type(value) is not int or -(2 ** 53 - 1) <= value <= 2 ** 53 - 1)


def _effect(effect):
    if type(effect) is not dict:
        _fail("invalid_effect", "Effect must be an object")
    kind = effect.get("kind")
    if type(kind) is not str or kind not in PERMISSION_FOR:
        _fail("unsupported_effect", "Only deterministic native narrative effects are permitted")
    if kind == "set_flag":
        _fields(effect, {"kind", "flag", "value"}, "set_flag")
        _identifier(effect["flag"], "story flag")
        if not _scalar(effect["value"]):
            _fail("invalid_effect", "set_flag requires a bounded scalar")
    elif kind == "add_flag":
        _fields(effect, {"kind", "flag", "amount"}, "add_flag")
        _identifier(effect["flag"], "story flag")
        if type(effect["amount"]) is not int or not -10000 <= effect["amount"] <= 10000:
            _fail("invalid_effect", "add_flag amount outside native limits")
    elif kind == "unlock_mission":
        _fields(effect, {"kind", "mission"}, "unlock_mission")
        _identifier(effect["mission"], "mission reference")
    elif kind == "gold":
        _fields(effect, {"kind", "amount"}, "gold")
        if type(effect["amount"]) is not int or not -10000 <= effect["amount"] <= 10000:
            _fail("invalid_effect", "gold amount outside native limits")
    return PERMISSION_FOR[kind]


def validate_script_manifest(document):
    """Strict, no-exec JSON; all permissions are derived from actual actions."""
    _fields(document, {"schema_version", "id", "namespace",
                       "sdk_api", "permissions", "hooks"}, "script")
    if type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA:
        _fail("unsupported_schema", "Explicit schema migration is required")
    _identifier(document["id"], "script ID")
    if type(document["namespace"]) is not str or not _NAMESPACE.fullmatch(document["namespace"]):
        _fail("invalid_script", "Expected reverse-domain namespace")
    try:
        negotiate_sdk(document["sdk_api"], required_features=(
            "sdk-negotiation.v1", "project-extensions.v1", "controlled-scripting.v1"))
    except SDKCompatibilityError as exc:
        raise StudioScriptError("incompatible_sdk", str(exc)) from exc
    hooks = document["hooks"]
    if type(hooks) is not list or not 1 <= len(hooks) <= MAX_HOOKS:
        _fail("invalid_script", "Expected 1..16 story-choice hooks")
    ids, targets, needed = set(), set(), set()
    for hook in hooks:
        _fields(hook, {"id", "trigger", "scene", "choice", "effects"}, "hook")
        _identifier(hook["id"], "hook ID")
        _identifier(hook["scene"], "scene ID")
        _identifier(hook["choice"], "choice ID")
        if hook["trigger"] != "story.choice":
            _fail("unsupported_hook", "Only story.choice is supported in R24.E")
        if hook["id"] in ids or (hook["scene"], hook["choice"]) in targets:
            _fail("duplicate_hook", "Duplicate hook ID or story-choice target")
        ids.add(hook["id"])
        targets.add((hook["scene"], hook["choice"]))
        effects = hook["effects"]
        if type(effects) is not list or not 1 <= len(effects) <= MAX_EFFECTS:
            _fail("invalid_script", "Expected 1..8 actions per hook")
        for effect in effects:
            needed.add(_effect(effect))
    provided = document["permissions"]
    if type(provided) is not list or any(
            type(p) is not str or p not in PERMISSIONS for p in provided
    ) or len(provided) != len(set(provided)) or set(provided) != needed:
        _fail("invalid_permission", "Permissions must match actual hook effects exactly")
    try:
        encoded = json.dumps(document, ensure_ascii=True, allow_nan=False,
                             sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise StudioScriptError("invalid_script", "Invalid JSON script") from exc
    if len(encoded) > MAX_BYTES:
        _fail("size_limit", "Script manifest exceeds 64 KiB")
    return deepcopy(document)


def _reject_duplicate_json_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            _fail("invalid_script", "Duplicate JSON key: " + key)
        out[key] = value
    return out


def read_script_manifest(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        _fail("unsafe_path", "A regular local JSON file is required")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            _fail("size_limit", "Script manifest too large")
        value = json.loads(raw.decode("utf-8"),
                           object_pairs_hook=_reject_duplicate_json_keys)
    except StudioScriptError:
        raise
    except (ValueError, OSError, UnicodeError, TypeError) as exc:
        raise StudioScriptError("invalid_script", str(exc)) from exc
    return validate_script_manifest(value)


def _exact_grants(declared, granted_permissions):
    if type(granted_permissions) not in (set, frozenset, tuple, list) or any(
            type(p) is not str for p in granted_permissions):
        _fail("permission_denied", "Explicit permission strings are required")
    if len(granted_permissions) != len(set(granted_permissions)) or (
            set(granted_permissions) != set(declared)):
        _fail("permission_denied", "All and only requested permissions must be approved")


def _bind(project, script):
    namespace = script["namespace"]
    extensions = project.setdefault("extensions", {})
    if namespace in extensions:
        _fail("already_installed", "Extension namespace already exists: " + namespace)
    # Other R24.E receipts own their story-choice hooks. Never overwrite
    # effects owned by a different declarative script without explicit merge.
    occupied = set()
    for spec in extensions.values():
        if type(spec) is dict and type(spec.get("data")) is dict and (
                spec["data"].get("kind") == "r24e.story-choice-hooks"):
            bindings = spec["data"].get("bindings", [])
            if type(bindings) is not list or any(type(row) is not dict for row in bindings):
                _fail("invalid_receipt", "Existing hook receipt has invalid bindings")
            for row in bindings:
                occupied.add((row.get("scene"), row.get("choice")))
    story = project.get("story")
    if type(story) is not dict or type(story.get("scenes")) is not list:
        _fail("missing_story", "Cannot install hooks without canonical story scenes")
    scene_map = {row["id"]: row for row in story["scenes"]}
    bindings = []
    for hook in script["hooks"]:
        target = (hook["scene"], hook["choice"])
        if target in occupied:
            _fail("hook_collision", "A different script already owns this story-choice hook")
        scene = scene_map.get(hook["scene"])
        if scene is None:
            _fail("missing_target", "Unknown story scene: " + hook["scene"])
        choice = next((row for row in scene["choices"]
                       if row["id"] == hook["choice"]), None)
        if choice is None:
            _fail("missing_target", "Unknown story choice: " + hook["choice"])
        before = choice.setdefault("effects", [])
        if len(before) + len(hook["effects"]) > 20:
            _fail("effect_limit", "Canonical scene choice is limited to 20 effects")
        index = len(before)
        appended = deepcopy(hook["effects"])
        before.extend(appended)
        bindings.append({"id": hook["id"], "scene": hook["scene"],
                         "choice": hook["choice"], "index": index,
                         "count": len(appended), "sha256": _digest(appended)})
    # Keep an inert, versioned audit receipt in the original GameProject.
    extensions[namespace] = {"schema_version": 1,
                             "data": {"kind": "r24e.story-choice-hooks",
                                      "script_id": script["id"],
                                      "source_sha256": _digest(script),
                                      "permissions": sorted(script["permissions"]),
                                      "bindings": bindings},
                             "references": []}
    return project


def preview_script(session: AuthoringSession, document, *,
                   granted_permissions=(), expected_revision=None):
    """Compile into native validated narrative effects; zero runtime interpreter."""
    if not isinstance(session, AuthoringSession):
        _fail("invalid_session", "Expected canonical AuthoringSession")
    script = validate_script_manifest(document)
    _exact_grants(script["permissions"], granted_permissions)
    if expected_revision is not None and (
            type(expected_revision) is not int or session.revision != expected_revision):
        _fail("stale_revision", "Editor changed; re-preview the manifest")
    return session.preview_project(
        lambda project: _bind(project, script), kind="r24e.story-choice-hooks")


def install_script(session: AuthoringSession, document, *,
                   granted_permissions=(), expected_revision=None):
    plan = preview_script(session, document, granted_permissions=granted_permissions,
                          expected_revision=expected_revision)
    return session.apply(plan)


def verify_compiled_scripts(project):
    """Report stale compiled-effect receipts, including after manual JSON edits.

    This read-only export gate never executes a hook or treats receipt hashes
    as cryptographic proof of publisher identity.
    """
    manifest = project.to_dict() if hasattr(project, "to_dict") else project
    errors = []
    try:
        if type(manifest) is not dict or type(manifest.get("story", {})) is not dict:
            _fail("invalid_project", "Expected a canonical GameProject document")
        extensions = manifest.get("extensions", {})
        if type(extensions) is not dict:
            _fail("invalid_project", "Invalid GameProject.extensions")
        stories = manifest.get("story", {}).get("scenes", [])
        if type(stories) is not list:
            _fail("invalid_project", "Invalid GameProject.story.scenes")
        known = {(scene["id"], choice["id"]): choice
                 for scene in stories for choice in scene["choices"]}
        seen = set()
        for namespace, extension in sorted(extensions.items()):
            if type(extension) is not dict or type(extension.get("data")) is not dict:
                continue
            info = extension["data"]
            if info.get("kind") != "r24e.story-choice-hooks":
                continue
            if (extension.get("schema_version") != 1 or
                    set(info) != {"kind", "script_id", "source_sha256",
                                  "permissions", "bindings"} or
                    type(info["bindings"]) is not list or
                    not 1 <= len(info["bindings"]) <= MAX_HOOKS):
                _fail("invalid_receipt", "Malformed controlled-hook receipt: " + namespace)
            _identifier(info["script_id"], "receipt script ID")
            hashes = (info["source_sha256"],)
            if any(type(h) is not str or not re.fullmatch(r"[0-9a-f]{64}", h)
                   for h in hashes):
                _fail("invalid_receipt", "Invalid source SHA-256 in " + namespace)
            if (type(info["permissions"]) is not list or
                    any(type(p) is not str or p not in PERMISSIONS
                        for p in info["permissions"]) or
                    len(info["permissions"]) != len(set(info["permissions"]))):
                _fail("invalid_receipt", "Invalid compiled-hook permissions")
            for binding in info["bindings"]:
                if type(binding) is not dict or set(binding) != {
                        "id", "scene", "choice", "index", "count", "sha256"}:
                    _fail("invalid_receipt", "Malformed hook binding")
                _identifier(binding["id"], "receipt hook ID")
                target = binding["scene"], binding["choice"]
                if (any(type(v) is not str for v in target) or
                        target in seen or target not in known):
                    _fail("invalid_receipt", "Duplicate/unknown hook target")
                seen.add(target)
                start, count = binding["index"], binding["count"]
                if (type(start) is not int or type(count) is not int or
                        start < 0 or not 1 <= count <= MAX_EFFECTS):
                    _fail("invalid_receipt", "Invalid hook range")
                effects = known[target].get("effects", [])
                if type(effects) is not list or start + count > len(effects):
                    _fail("stale_compilation", "Compiled hook was removed: " + str(target))
                actual = effects[start:start + count]
                expected = binding["sha256"]
                if (type(expected) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected)
                        or _digest(actual) != expected):
                    _fail("stale_compilation", "Compiled effects differ: " + str(target))
    except (StudioScriptError, TypeError, KeyError, ValueError,
            UnicodeError, RecursionError) as exc:
        errors.append("Controlled scripting: " + str(exc))
    return errors
