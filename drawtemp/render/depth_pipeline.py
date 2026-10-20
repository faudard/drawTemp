"""R52.A bounded visual-depth contract for the shared R3 Qt Quick renderer.

Decorations are optical-only. They must NEVER feed terrain/actor picking,
Core ticks, Content, GameSession, save files or collision calculations.
Nothing in this module creates another renderer or selects a physical GPU.
"""
from collections.abc import Mapping
from math import isfinite
import re


PROFILE_VERSION = 1
MAX_LAYERS = 8
MAX_LAYER_SIDE = 2048
PROJECTIONS = ("isometric", "top_down")
_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
_ID = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")


def _number(value, field, lo, hi):
    if type(value) not in (int, float) or not isfinite(value) or not lo <= value <= hi:
        raise ValueError(field + " must be a finite number in [%s, %s]" % (lo, hi))
    return float(value)


def normalize_depth_profile(profile=None, *, projection_mode="isometric"):
    """Copy and strictly validate an opt-in, presentation-only R52.A profile.

    In particular, projection is not switchable through this cosmetic contract:
    a mismatched mode is rejected rather than silently changing picking.
    External image URLs, shaders and arbitrary effect payloads are not allowed.
    """
    if projection_mode not in PROJECTIONS:
        raise ValueError("Unknown renderer projection")
    if profile is None:
        profile = {}
    if not isinstance(profile, Mapping):
        raise ValueError("Depth profile must be an object")
    if set(profile) - {"version", "projection", "layers", "effects"}:
        raise ValueError("Unknown depth profile fields")
    if type(profile.get("version", PROFILE_VERSION)) is not int or profile.get("version", PROFILE_VERSION) != PROFILE_VERSION:
        raise ValueError("Unsupported depth profile version")
    if profile.get("projection", projection_mode) != projection_mode:
        raise ValueError("Depth profile projection must match the shared renderer")
    entries = profile.get("layers", [])
    if not isinstance(entries, (list, tuple)) or len(entries) > MAX_LAYERS:
        raise ValueError("Depth layers must be a bounded array")
    layers = []
    identifiers = set()
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != {
                "id", "x", "y", "width", "height", "parallax", "color", "opacity"}:
            raise ValueError("Invalid depth layer fields")
        identifier = entry["id"]
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier) or identifier in identifiers:
            raise ValueError("Invalid or duplicate depth layer ID")
        identifiers.add(identifier)
        color = entry["color"]
        if not isinstance(color, str) or not _COLOR.fullmatch(color):
            raise ValueError("Depth layer color must be #RRGGBB")
        layers.append({
            "id": identifier,
            "x": _number(entry["x"], "x", -100000, 100000),
            "y": _number(entry["y"], "y", -100000, 100000),
            "width": _number(entry["width"], "width", 1, MAX_LAYER_SIDE),
            "height": _number(entry["height"], "height", 1, MAX_LAYER_SIDE),
            "parallax": _number(entry["parallax"], "parallax", 0, 1),
            "color": color.lower(),
            "opacity": _number(entry["opacity"], "opacity", 0, 1),
        })
    effects = profile.get("effects", {})
    if not isinstance(effects, Mapping) or set(effects) - {"lightmap", "shadows"}:
        raise ValueError("Invalid depth effects")
    normalized_effects = {}
    for name in ("lightmap", "shadows"):
        requested = effects.get(name, False)
        if type(requested) is not bool:
            raise ValueError("Depth effect switches must be boolean")
        normalized_effects[name] = requested
    return {"version": PROFILE_VERSION, "projection": projection_mode,
            "layers": layers, "effects": normalized_effects}


def projected_depth_layers(profile, projection):
    """R3 projection coordinates for QML; no camera offsets or game edits.

    Qt Quick applies camera.pan*parallax for the decorative pass only.
    World geometry and picking use the original camera with factor 1.
    """
    result = []
    for index, layer in enumerate(profile["layers"]):
        sx, sy = projection.project(layer["x"], layer["y"])
        result.append({"id": layer["id"], "sx": sx, "sy": sy,
                       "width": layer["width"], "height": layer["height"],
                       "parallax": layer["parallax"], "color": layer["color"],
                       "opacity": layer["opacity"], "depthIndex": index})
    return result


def world_to_screen(camera, projection, x, y, *, elevation=0):
    """The only interactive conversion; never applies decorative parallax."""
    return camera.screen(*projection.project(x, y, elevation))


def screen_to_world(camera, projection, sx, sy, *, elevation=0):
    """Inverse of world_to_screen for a known elevation plane."""
    return projection.unproject(*camera.world(sx, sy), elevation)


def decoration_screen_point(camera, projection, x, y, *, parallax):
    """Visual-only anchor matching the Qt Quick layer formula."""
    factor = _number(parallax, "parallax", 0, 1)
    sx, sy = projection.project(x, y)
    return (camera.width / 2 + (camera.pan_x + sx * camera.zoom) * factor,
            camera.height / 2 + (camera.pan_y + sy * camera.zoom) * factor)


def effect_capabilities(profile):
    """R52.A fail-closed report: no shader/lightmap/shadow pass is shipped.

    R52.B may negotiate actual renderer capabilities and add implementation;
    never advertise a requested effect as enabled merely because it was parsed.
    """
    requested = profile["effects"]
    return {"lightmapEnabled": False, "shadowsEnabled": False,
            "lightmapFallback": "not-implemented-r52b" if requested["lightmap"] else "",
            "shadowsFallback": "not-implemented-r52b" if requested["shadows"] else ""}


def backend_plan(requested, *, hardware_available, software_available):
    """Advisory only; real Qt RHI selection is owned by Qt before engine init.

    This pure function records how a host should fail closed. It does not
    configure Qt, detect a GPU or claim that a physical device was tested.
    """
    if requested not in ("auto", "hardware", "software"):
        raise ValueError("Invalid requested backend")
    if type(hardware_available) is not bool or type(software_available) is not bool:
        raise ValueError("Backend capabilities must be booleans")
    if requested != "software" and hardware_available:
        return {"backend": "hardware", "fallback": ""}
    if software_available:
        return {"backend": "software",
                "fallback": "hardware-unavailable" if requested != "software" else ""}
    raise RuntimeError("No permitted Qt Quick backend is available")
