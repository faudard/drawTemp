"""Canonical, opt-in 2D visual layers stored in GameProject.extensions.

Independent of tactical Content, physics/collision and editor-only layer
visibility preferences. A cell has a material sprite and four independent
0..255 alpha mask quadrants. Stacking and actor-depth planes are explicit.
No execution hooks, file paths or arbitrary image URIs are allowed.
"""
from __future__ import annotations

from copy import deepcopy
import re

from .model import RuleError, require

VISUAL_NS = "org.drawtemp.visuallayers"
MATERIALS = ("grass", "dirt", "sand", "stone", "cobble", "rock", "water", "bridge")
PLANES = ("below", "above")
MAX_LAYERS = 16
MAX_CELLS = 640  # Bounds the extension's 64 KiB canonical JSON envelope.
_ID = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")


def _mission_sizes(content):
    return {ident: (mission.board.width, mission.board.height)
            for ident, mission in content.missions.items()}


def validate_visual_layers(data, content):
    """Validate and detach the version-one visual catalog; fail closed."""
    require(type(data) is dict and set(data) == {"missions"},
            "Visual layers need one missions dictionary")
    missions = data["missions"]
    require(type(missions) is dict and len(missions) <= 128,
            "Invalid visual layer mission mapping")
    dimensions = _mission_sizes(content)
    total_cells = 0
    for mid, stack in missions.items():
        require(mid in dimensions, "Unknown visual layer mission: " + str(mid))
        require(type(stack) is list and len(stack) <= MAX_LAYERS,
                "Maximum 16 visual layers per mission")
        layer_ids = set()
        width, height = dimensions[mid]
        for layer in stack:
            require(type(layer) is dict and set(layer) ==
                    {"id", "name", "visible", "locked", "opacity", "plane", "cells"},
                    "Invalid visual layer fields")
            ident = layer["id"]
            require(type(ident) is str and _ID.fullmatch(ident) is not None and
                    ident not in layer_ids, "Duplicate or invalid visual layer ID")
            layer_ids.add(ident)
            require(type(layer["name"]) is str and
                    1 <= len(layer["name"].strip()) <= 64,
                    "Visual layer name must contain 1..64 characters")
            require(type(layer["visible"]) is bool and type(layer["locked"]) is bool,
                    "Visual layer visibility and lock must be boolean")
            require(type(layer["opacity"]) is int and 0 <= layer["opacity"] <= 100,
                    "Visual layer opacity must be 0..100")
            require(layer["plane"] in PLANES, "Invalid visual layer depth plane")
            cells = layer["cells"]
            require(type(cells) is list, "Visual layer cells must be a list")
            total_cells += len(cells)
            require(total_cells <= MAX_CELLS, "Visual layer cell budget exceeded")
            positions = set()
            for item in cells:
                require(type(item) is dict and set(item) == {"pos", "material", "mask"},
                        "Invalid visual layer cell")
                xy = item["pos"]
                require(type(xy) is list and len(xy) == 2 and
                        all(type(n) is int for n in xy) and
                        0 <= xy[0] < width and 0 <= xy[1] < height,
                        "Visual cell position outside map")
                require(tuple(xy) not in positions, "Duplicate visual cell in layer")
                positions.add(tuple(xy))
                require(type(item["material"]) is str and
                        item["material"] in MATERIALS, "Invalid visual material")
                mask = item["mask"]
                require(type(mask) is list and len(mask) == 4 and
                        all(type(alpha) is int and 0 <= alpha <= 255
                            for alpha in mask), "Mask needs four 0..255 alpha values")
    return deepcopy(data)


def from_extensions(extensions, content=None):
    """Legacy projects have no visual layer stack and no schema migration."""
    spec = extensions.get(VISUAL_NS)
    if spec is None:
        return {"missions": {}}
    if content is not None:
        return validate_visual_layers(spec["data"], content)
    return deepcopy(spec["data"])


def attach_visual_layers(scene, extensions):
    """Detach per-mission art to the R3 render scene without changing gameplay."""
    catalog = from_extensions(extensions)
    mid = scene.get("mission")
    # The Player may render world/exploration scenes without a tactical map ID.
    selected = catalog["missions"].get(mid, [])
    result = dict(scene)
    result["visual_layers"] = deepcopy(selected)
    return result


def visual_image_key(material, mask, variant=0):
    """Bounded URL key consumed by the existing 2D atlas image provider."""
    require(material in MATERIALS and type(variant) is int and variant in (0, 1)
            and len(mask) == 4 and
            all(type(v) is int and 0 <= v <= 255 for v in mask),
            "Invalid graphic sprite key")
    return "v" + str(MATERIALS.index(material)) + str(variant) + "".join(
        f"{alpha:02x}" for alpha in mask)


def projected_layer_rows(scene, projection, visible_bounds):
    """Bounded cosmetic render rows; QML never interprets the authored schema.

    R3 z-order: terrain behind all; lower-plane art below characters and
    objects, upper-plane art above. Relative list position orders layers in
    the same plane, and 0 <= z-fraction < 1 protects the per-row depth gap.
    """
    from drawtemp.render.iso_scene import TopDownProjection

    if not isinstance(projection, TopDownProjection):
        return []
    lo_x, hi_x, lo_y, hi_y = visible_bounds
    rows = []
    elevations = {(t["x"], t["y"]): t["height"] for t in scene["tiles"]}
    for index, layer in enumerate(scene.get("visual_layers", ())):
        if not layer["visible"] or layer["opacity"] == 0:
            continue
        depth = 10 if layer["plane"] == "below" else 90
        for item in layer["cells"]:
            x, y = item["pos"]
            if not lo_x <= x <= hi_x or not lo_y <= y <= hi_y:
                continue
            if not any(item["mask"]):
                continue
            z = elevations.get((x, y), 0)
            sx, sy = projection.project(x, y, z)
            rows.append({
                "kind": "visual-layer",
                "id": f"visual:{layer['id']}:{x}:{y}",
                "layerId": layer["id"],
                "x": x, "y": y, "sx": sx, "sy": sy,
                "material": item["material"],
                "mask": list(item["mask"]),
                "visualKey": visual_image_key(item["material"], item["mask"],
                                              (x * 17 + y * 29) & 1),
                "opacity": layer["opacity"] / 100.0,
                "zOrder": y * 100 + depth + index / (MAX_LAYERS + 1),
            })
    return rows


__all__ = ["VISUAL_NS", "MATERIALS", "PLANES", "MAX_LAYERS", "MAX_CELLS",
           "validate_visual_layers", "from_extensions", "attach_visual_layers",
           "projected_layer_rows", "visual_image_key"]
