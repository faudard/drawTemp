"""V3 declarative event addons compiled into canonical StoryBook choices.

There is no runtime plugin callback/interpreter. The existing R24.E native
compiler owns authoring transactions, receipts and deterministic replay.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.addons import AddonError, validate_addon_manifest
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.controlled_scripting import (
    PERMISSION_FOR, StudioScriptError, preview_script, validate_script_manifest,
    verify_compiled_scripts,
)
from drawtemp.sdk import SDK_API_VERSION

POINT = "game.event"
REQUIRED_FEATURE = "event-addons.v1"


class EventAddonError(AddonError):
    """Stable errors for declarative event addon preflight."""


def _fail(code, detail):
    raise EventAddonError(code, detail)


def event_addon_script(manifest):
    """Build a strictly validated, bounded R24.E script from a v3 manifest.

    Only native story.choice hooks and their four deterministic, allowlisted
    effects are supported. A v3 event grant permits *only this compilation*;
    it does not grant arbitrary game state mutation or Python execution.
    """
    manifest = validate_addon_manifest(manifest)
    contributions = [
        contribution for contribution in manifest["contributions"]
        if contribution["point"] == POINT
    ]
    if not contributions:
        return None
    if REQUIRED_FEATURE not in manifest["sdk"]["required_features"]:
        _fail("missing_feature", "game.event requires event-addons.v1")
    # SDK capability negotiation already validated in the v3 manifest.
    if len(contributions) > 16:
        _fail("hook_limit", "At most 16 native story-choice event hooks")
    hooks, required = [], set()
    for contribution in contributions:
        config = contribution["config"]
        if type(config) is not dict or set(config) != {
                "trigger", "scene", "choice", "effects"}:
            _fail("invalid_event", "game.event requires trigger, scene, choice, effects")
        if config["trigger"] != "story.choice":
            _fail("unsupported_trigger", "Only story.choice event hooks are supported")
        effects = config["effects"]
        if type(effects) is not list or not 1 <= len(effects) <= 8:
            _fail("effect_limit", "Each hook requires 1..8 native effects")
        for effect in effects:
            if type(effect) is not dict or effect.get("kind") not in PERMISSION_FOR:
                _fail("unsupported_effect", "Use a deterministic R24.E effect")
            required.add(PERMISSION_FOR[effect["kind"]])
        hooks.append({
            "id": contribution["id"],
            "trigger": "story.choice",
            "scene": config["scene"],
            "choice": config["choice"],
            "effects": deepcopy(effects),
        })
    source = {
        "schema_version": 1,
        "id": manifest["id"],
        "namespace": manifest["namespace"],
        "sdk_api": list(SDK_API_VERSION),
        "permissions": sorted(required),
        "hooks": hooks,
    }
    try:
        return validate_script_manifest(source)
    except StudioScriptError as exc:
        raise EventAddonError(exc.code, str(exc)) from exc


def _enabled_source(manager, addon_id):
    status = manager.status(addon_id)
    if status["format"] != "addon-v3":
        _fail("legacy_read_only", "Legacy mods cannot run as event addons")
    if not status["enabled"] or "events.write" not in status["grants"]:
        _fail("permission_denied", "Explicitly enable the event addon first")
    script = event_addon_script(manager.manifest(addon_id))
    if script is None:
        _fail("no_event_points", "Addon has no game.event contributions")
    return script


def event_addon_catalogue(manager):
    """Host/editor metadata only; disabled manifests cannot supply commands."""
    result = []
    for status in manager.statuses():
        if status["format"] != "addon-v3" or not status["enabled"]:
            continue
        if "game.event" not in status["capabilities"]:
            continue
        script = _enabled_source(manager, status["id"])
        for hook in script["hooks"]:
            result.append({
                "addon_id": status["id"],
                "id": hook["id"],
                "trigger": hook["trigger"],
                "scene": hook["scene"],
                "choice": hook["choice"],
                "effects": deepcopy(hook["effects"]),
            })
    return tuple(result)


def preview_event_addon(manager, session: AuthoringSession, addon_id, *,
                        expected_revision=None):
    """Return a revision-bound AuthoringPlan, never a live runtime callback."""
    script = _enabled_source(manager, addon_id)
    try:
        return preview_script(
            session, script, granted_permissions=script["permissions"],
            expected_revision=expected_revision,
        )
    except StudioScriptError as exc:
        raise EventAddonError(exc.code, str(exc)) from exc


def install_event_addon(manager, session: AuthoringSession, addon_id, *,
                        expected_revision=None):
    """Compile atomically; one Undo/Redo entry, no implicit disk write."""
    plan = preview_event_addon(
        manager, session, addon_id, expected_revision=expected_revision
    )
    return session.apply(plan)


def verify_runtime_event_receipts(project):
    """Player preflight for compiled native hooks, including R24.E originals.

    Unknown/uninstalled add-on metadata is not needed to run compiled games.
    Modified or missing native effect receipts fail closed.
    """
    return verify_compiled_scripts(project)
