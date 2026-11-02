"""Safe, headless v3 Studio extension point contracts.

The host interprets only fixed native Qt UI templates and existing commands.
No add-on callback, Python module, QML source or arbitrary file path is read.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.addons import AddonError
from drawtemp.studio.map_authoring import SURFACE_PALETTE

PROJECT_FIELDS = frozenset({
    "project.title", "project.campaign_count", "content.mission_count",
})
MENU_COMMANDS = frozenset({
    "go_maps", "go_actors", "go_events", "global_search", "focus_inspector",
})
STUDIO_POINTS = frozenset({"studio.dock", "studio.menu", "studio.tool"})
_SHAPES = frozenset({"diamond", "square"})


class StudioAddonPointError(AddonError):
    pass


def _fail(message):
    raise StudioAddonPointError("invalid_studio_point", message)


def _fields(config, expected, label):
    if type(config) is not dict or set(config) != set(expected):
        _fail(label + " must contain exactly " + ", ".join(sorted(expected)))


def _label(value, name):
    if (type(value) is not str or not value.strip() or
            len(value) > 100 or any(ord(c) < 32 for c in value)):
        _fail("Invalid " + name + " label")


def validate_studio_contribution(contribution):
    """Return detached, host-safe metadata; reject unknown point configurations."""
    if type(contribution) is not dict:
        _fail("Expected a contribution object")
    point, config = contribution.get("point"), contribution.get("config")
    if point not in STUDIO_POINTS:
        _fail("Unsupported Studio extension point: " + str(point))
    if point == "studio.dock":
        _fields(config, {"title", "fields"}, point)
        _label(config["title"], "dock")
        fields = config["fields"]
        if (type(fields) is not list or not fields or len(fields) > 8 or
                any(type(v) is not str or v not in PROJECT_FIELDS for v in fields)
                or len(fields) != len(set(fields))):
            _fail("Dock fields must be unique, supported read-only project fields")
    elif point == "studio.menu":
        _fields(config, {"label", "command"}, point)
        _label(config["label"], "menu")
        if type(config["command"]) is not str or config["command"] not in MENU_COMMANDS:
            _fail("Menu command is not a host-owned allowlisted action")
    else:
        _fields(config, {"label", "material", "radius", "shape"}, point)
        _label(config["label"], "tool")
        if type(config["material"]) is not str or config["material"] not in SURFACE_PALETTE:
            _fail("Unknown map surface")
        if type(config["radius"]) is not int or not 0 <= config["radius"] <= 3:
            _fail("Map brush radius must be 0..3")
        if type(config["shape"]) is not str or config["shape"] not in _SHAPES:
            _fail("Unknown brush shape")
    return deepcopy(contribution)


def studio_contributions(manager):
    """Flatten enabled add-ons in deterministic order; reject partial invalid sets.

    Disabled and legacy manifests yield nothing. Only v3 Studio contributions
    are considered. Existing R24 plugin docks remain managed by R24.
    """
    result = []
    for status in manager.statuses():
        if not status["enabled"] or status["format"] != "addon-v3":
            continue
        manifest = manager.manifest(status["id"])
        for contribution in manifest["contributions"]:
            if contribution["point"] in STUDIO_POINTS:
                valid = validate_studio_contribution(contribution)
                result.append({
                    "addon_id": status["id"], "id": valid["id"],
                    "point": valid["point"], "config": valid["config"],
                })
    return tuple(result)


def project_field_values(snapshot):
    """Detach only a bounded read-only view of canonical session data."""
    project = snapshot.project
    content = snapshot.content
    return {
        "project.title": str(project.get("title", ""))[:200],
        "project.campaign_count": len(project.get("campaigns", ())),
        "content.mission_count": len(content.get("missions", ())),
    }
