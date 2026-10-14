"""DrawTemp 5 R7: presentation-only character authoring and portable asset export.

Character documents are *authoring recipes*. The runtime output is the
existing sporebound.assets.AssetRegistry v1 (sprites/animations/portraits).
Neither Content/GameProject nor tactical saves/replays are changed.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import argparse
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from sporebound.assets import AssetRegistry, _portable_path

DIRECTIONS = ("south", "north", "east", "west")
ACTIONS = ("idle", "walk", "run", "attack", "magic", "hit", "block", "death", "victory")
SLOTS = ("body", "face", "eyes", "hair", "clothing", "cape", "weapon", "accessory")
MANDATORY = ("idle", "walk", "attack")
ID_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{6}\Z")


class CharacterError(ValueError):
    """Invalid character recipe or an export that cannot be completed."""


def _check(condition, message):
    if not condition:
        raise CharacterError(message)


def _identifier(value, field="identifier"):
    _check(isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None,
           "Invalid " + field + ": " + str(value))


def _path(value):
    try:
        _portable_path(value)
    except Exception as exc:
        raise CharacterError(str(exc)) from exc
    _check(Path(value).suffix.lower() == ".png", "Expected a portable PNG path")


def _point(value, field, *, low=-4096, high=4096):
    _check(isinstance(value, list) and len(value) == 2
           and all(type(x) is int and low <= x <= high for x in value),
           field + " must contain two integers")
    return value


def _rect(value):
    _check(isinstance(value, list) and len(value) == 4
           and all(type(x) is int and x >= 0 for x in value)
           and value[2] > 0 and value[3] > 0,
           "Region must be [x,y,width,height]")
    return value


def validate(document):
    """Validate recipe schema without requiring Pillow or loading artwork."""
    _check(isinstance(document, dict)
           and set(document) == {"version", "id", "name", "size", "pivot", "variants"},
           "Invalid character document fields")
    _check(type(document["version"]) is int and document["version"] == 1,
           "Unsupported character recipe version")
    _identifier(document["id"], "character id")
    _check(isinstance(document["name"], str) and document["name"].strip(),
           "Character name is required")
    width, height = _point(document["size"], "Canvas size", low=1, high=2048)
    px, py = _point(document["pivot"], "Foot pivot", low=0, high=2048)
    _check(px < width and py < height, "Pivot must be inside the canvas")
    variants = document["variants"]
    _check(isinstance(variants, dict) and 1 <= len(variants) <= 32,
           "At least one variant and at most 32 are required")
    for variant_id, variant in variants.items():
        _identifier(variant_id, "outfit id")
        _check(isinstance(variant, dict)
               and set(variant) == {"name", "clips", "layers", "expressions"},
               "Invalid outfit fields: " + variant_id)
        _check(isinstance(variant["name"], str) and variant["name"].strip(),
               "Outfit name is required")
        layers = variant["layers"]
        _check(isinstance(layers, list) and len(layers) <= 24, "Invalid appearance layers")
        seen = set()
        for layer in layers:
            _check(isinstance(layer, dict)
                   and set(layer) == {"slot", "paths", "offset", "tint", "opacity"},
                   "Invalid modular layer")
            _check(layer["slot"] in SLOTS and layer["slot"] not in seen,
                   "Duplicate or unknown appearance slot")
            seen.add(layer["slot"])
            _check(isinstance(layer["paths"], dict)
                   and set(layer["paths"]) <= set(DIRECTIONS),
                   "Invalid directional layer paths")
            for path in layer["paths"].values():
                _path(path)
            _point(layer["offset"], "Layer offset")
            _check(isinstance(layer["tint"], str)
                   and COLOR_PATTERN.fullmatch(layer["tint"]), "Invalid layer tint")
            _check(type(layer["opacity"]) is int and 0 <= layer["opacity"] <= 255,
                   "Layer opacity must be 0..255")
        expressions = variant["expressions"]
        _check(isinstance(expressions, dict) and len(expressions) <= 32,
               "Invalid expressions")
        for expression, path in expressions.items():
            _identifier(expression, "expression")
            _path(path)
        clips = variant["clips"]
        _check(isinstance(clips, dict) and set(clips) <= set(ACTIONS), "Unknown action")
        for action, clip in clips.items():
            _check(isinstance(clip, dict) and set(clip) == {"loop", "directions"},
                   "Invalid clip: " + action)
            _check(type(clip["loop"]) is bool, "Loop must be boolean")
            _check(isinstance(clip["directions"], dict)
                   and set(clip["directions"]) <= set(DIRECTIONS), "Unknown direction")
            for direction, frames in clip["directions"].items():
                _check(isinstance(frames, list) and 1 <= len(frames) <= 128,
                       "Each defined clip needs 1..128 frames")
                for frame in frames:
                    _check(isinstance(frame, dict)
                           and set(frame) == {"path", "region", "offset", "duration_ms"},
                           "Invalid animation keyframe")
                    _path(frame["path"])
                    if frame["region"] is not None:
                        _rect(frame["region"])
                    _point(frame["offset"], "Frame offset")
                    _check(type(frame["duration_ms"]) is int
                           and 16 <= frame["duration_ms"] <= 60000,
                           "Frame duration must be 16..60000 ms")
    return deepcopy(document)


def frame(path, *, region=None, duration_ms=160, offset=(0, 0)):
    return {"path": path, "region": list(region) if region is not None else None,
            "duration_ms": duration_ms, "offset": list(offset)}


def atlas_variant(name, path, *, rows, size=(64, 64), column_order=DIRECTIONS):
    """Turn existing directional atlas cells into editable, timed clips."""
    clips = {}
    for action, indices in rows.items():
        clips[action] = {
            "loop": action in ("idle", "walk", "run"),
            "directions": {
                direction: [
                    frame(path, region=[col * size[0], row * size[1], *size],
                          duration_ms=180 if action == "walk" else 140)
                    for row in indices
                ]
                for col, direction in enumerate(column_order)
            },
        }
    return {"name": name, "clips": clips, "layers": [], "expressions": {}}


def starter_library():
    """Actual existing atlas data, not invented 4-direction watercolor poses."""
    atlas = "sporebound/content/art/jeanne/jeanne_atlas.png"
    jeanne = {
        "version": 1, "id": "jeanne", "name": "Jeanne d'Arc",
        "size": [64, 64], "pivot": [32, 63],
        "variants": {
            "historical": atlas_variant("Jeanne — atlas existant", atlas,
                rows={"idle": [0, 1], "walk": [2, 3], "attack": [4, 5],
                      "hit": [6], "death": [7]})
        },
    }
    jeanne["variants"]["historical"]["expressions"] = {
        "neutral": "sporebound/content/art/jeanne/jeanne_neutral.png",
        "smile": "sporebound/content/art/jeanne/jeanne_smile.png",
        "determined": "sporebound/content/art/jeanne/jeanne_determined.png",
    }
    generic_atlas = "sporebound/content/art/iso/chibi_actors.png"
    library = {"jeanne": validate(jeanne)}
    for key, title, row in (
        ("villager", "Villageois (prototype)", 0),
        ("knight", "Chevalier (prototype)", 1),
        ("archer", "Archer (prototype)", 2),
    ):
        # Generic atlas columns contain TWO frames per direction, rows are styles.
        clips = {
            action: {"loop": True, "directions": {
                direction: [frame(generic_atlas,
                    region=[(col * 2 + offset) * 64, row * 64, 64, 64],
                    duration_ms=180) for offset in indices]
                for col, direction in enumerate(DIRECTIONS)}}
            for action, indices in (("idle", (0,)), ("walk", (0, 1)))
        }
        library[key] = validate({
            "version": 1, "id": key, "name": title, "size": [64, 64],
            "pivot": [32, 63],
            "variants": {"default": {
                "name": "Base", "clips": clips, "layers": [], "expressions": {}}}
        })
    return library


def diagnostics(document, *, require_outfits=False):
    """Machine-readable art QA; incomplete production content is never hidden."""
    data = validate(document)
    issues = []
    variants = data["variants"]
    for vid, variant in variants.items():
        for action in MANDATORY:
            for direction in DIRECTIONS:
                if not variant["clips"].get(action, {}).get("directions", {}).get(direction):
                    issues.append({"severity": "error", "variant": vid,
                                   "code": "missing_animation", "action": action,
                                   "direction": direction})
        for action in ACTIONS:
            if action not in variant["clips"]:
                issues.append({"severity": "warning", "variant": vid,
                               "code": "missing_action", "action": action})
        if not variant["expressions"]:
            issues.append({"severity": "warning", "variant": vid,
                           "code": "missing_portrait"})
    if require_outfits and data["id"] == "jeanne":
        for outfit in ("peasant", "armor"):
            if outfit not in variants:
                issues.append({"severity": "error", "variant": outfit,
                               "code": "missing_outfit"})
        # An outfit is not distinct because it was given a different name.
        if "peasant" in variants and "armor" in variants:
            a, b = variants["peasant"], variants["armor"]
            if a["clips"] == b["clips"] and a["layers"] == b["layers"]:
                issues.append({"severity": "error", "code": "identical_outfits"})
    return issues


@dataclass(frozen=True)
class Preview:
    revision: int
    owner: object
    document: dict


class CharacterSession:
    """Undoable authoring: previews cannot overwrite intervening changes."""
    def __init__(self, document, *, history_limit=60):
        self._document = validate(document)
        self._revision = 0
        self._owner = object()
        self._undo = []
        self._redo = []
        self._limit = history_limit

    @property
    def revision(self):
        return self._revision

    @property
    def document(self):
        return deepcopy(self._document)

    def preview(self, transform):
        candidate = deepcopy(self._document)
        transform(candidate)
        return Preview(self._revision, self._owner, validate(candidate))

    def commit(self, preview):
        if preview.owner is not self._owner or preview.revision != self._revision:
            raise CharacterError("Stale or foreign character edit")
        candidate = validate(preview.document)
        if candidate == self._document:
            raise CharacterError("No changes")
        self._undo.append(self._document)
        del self._undo[:-self._limit]
        self._document = candidate
        self._redo.clear()
        self._revision += 1

    def edit(self, transform):
        self.commit(self.preview(transform))

    def undo(self):
        if not self._undo:
            return False
        self._redo.append(self._document)
        self._document = self._undo.pop()
        self._revision += 1
        return True

    def redo(self):
        if not self._redo:
            return False
        self._undo.append(self._document)
        self._document = self._redo.pop()
        self._revision += 1
        return True


def _resolved(root, path):
    base = Path(root).resolve()
    target = (base / path).resolve()
    _check(target.is_relative_to(base) and target.is_file(),
           "Missing/unsafe image: " + path)
    return target


def render_frame(document, variant_id, action, direction, index, root):
    """Composite the exact frame that export uses. Pillow is optional at import."""
    from PIL import Image, ImageChops
    data = validate(document)
    variant = data["variants"][variant_id]
    entry = variant["clips"][action]["directions"][direction][index]
    canvas = Image.new("RGBA", tuple(data["size"]), (0, 0, 0, 0))
    with Image.open(_resolved(root, entry["path"])) as source:
        source = source.convert("RGBA")
        region = entry["region"]
        if region is not None:
            x, y, w, h = region
            _check(x + w <= source.width and y + h <= source.height,
                   "Atlas region exceeds actual PNG bounds")
            source = source.crop((x, y, x + w, y + h))
        _check(source.size == tuple(data["size"]),
               "Source frame size differs from character canvas")
        canvas.alpha_composite(source, tuple(entry["offset"]))
    for layer in variant["layers"]:
        path = layer["paths"].get(direction)
        if not path:
            continue
        with Image.open(_resolved(root, path)) as src:
            overlay = src.convert("RGBA")
            _check(overlay.size == tuple(data["size"]),
                   "Layer canvas size must match character canvas")
            rgb = tuple(int(layer["tint"][i:i+2], 16) for i in (1, 3, 5))
            if rgb != (255, 255, 255):
                # Preserve detail in alpha; RGB tint uses multiplication.
                solid = Image.new("RGB", overlay.size, rgb)
                tinted_rgb = ImageChops.multiply(overlay.convert("RGB"), solid)
                overlay = Image.merge("RGBA", (*tinted_rgb.split(),
                                               overlay.getchannel("A")))
            if layer["opacity"] != 255:
                overlay.putalpha(overlay.getchannel("A").point(
                    lambda alpha: alpha * layer["opacity"] // 255))
            canvas.alpha_composite(overlay, tuple(layer["offset"]))
    return canvas


def export_pack(document, root, destination, *, strict=False):
    """Export reproducible PNG atlas + canonical AssetRegistry v1.

    No modification to source artwork. Destination must not be inside root's
    source art directories; files are staged and individually atomically
    replaced. Existing registry is not edited or overwritten.
    """
    from PIL import Image
    data = validate(document)
    errors = [issue for issue in diagnostics(data, require_outfits=strict)
              if issue["severity"] == "error"]
    if errors:
        raise CharacterError("Art QA failed: " + json.dumps(errors, ensure_ascii=False))
    root, destination = Path(root).resolve(), Path(destination).resolve()
    _check(destination != root and not root.is_relative_to(destination),
           "Refusing export over the source repository")
    _check(not destination.is_relative_to(root / "sporebound" / "content")
           and not destination.is_relative_to(root / "assets"),
           "Export must not overwrite the authored asset directories")
    output = []
    for variant_id, variant in sorted(data["variants"].items()):
        for action, clip in sorted(variant["clips"].items()):
            for direction, frames in sorted(clip["directions"].items()):
                for index in range(len(frames)):
                    output.append((variant_id, action, direction, index,
                                   render_frame(data, variant_id, action,
                                                direction, index, root)))
    _check(output, "No frames to export")
    width, height = data["size"]
    columns = min(8, len(output))
    rows = (len(output) + columns - 1) // columns
    _check(width * columns <= 8192 and height * rows <= 16384,
           "Atlas exceeds export size limits")
    atlas = Image.new("RGBA", (width * columns, height * rows))
    entries, bindings, clips = [], {}, {}
    for i, (variant_id, action, direction, index, image) in enumerate(output):
        x, y = (i % columns) * width, (i // columns) * height
        atlas.alpha_composite(image, (x, y))
        sprite_id = f"{data['id']}_{variant_id}_{action}_{direction}_{index:03d}"
        entries.append({"id": sprite_id, "kind": "sprite",
                        "path": "atlas.png", "region": [x, y, width, height]})
        clips.setdefault((variant_id, action, direction), []).append(
            {"sprite": sprite_id, "duration_ms":
             data["variants"][variant_id]["clips"][action]
                 ["directions"][direction][index]["duration_ms"]})
    for (vid, action, direction), frames in sorted(clips.items()):
        anim_id = f"anim_{data['id']}_{vid}_{action}_{direction}"
        entries.append({"id": anim_id, "kind": "animation",
                        "loop": data["variants"][vid]["clips"][action]["loop"],
                        "frames": frames})
        bindings[anim_id] = anim_id
    portraits = {}
    for vid, variant in sorted(data["variants"].items()):
        for expression, path in sorted(variant["expressions"].items()):
            aid = f"portrait_{data['id']}_{vid}_{expression}"
            rel = f"{aid}.png"
            entries.append({"id": aid, "kind": "portrait", "path": rel})
            portraits[rel] = _resolved(root, path)
    registry = {"version": 1, "entries": entries,
                "bindings": {"animation": bindings}}
    AssetRegistry(registry)  # Existing runtime validator is the final gate.
    metadata = {"version": 1, "character_id": data["id"],
                "variants": sorted(data["variants"]), "pivot": data["pivot"],
                "size": data["size"], "directions": list(DIRECTIONS),
                "registry": "registry.json",
                "diagnostics": diagnostics(data)}
    destination.mkdir(parents=True, exist_ok=True)
    # Generate all payloads before publication. Never delete unrelated files.
    with tempfile.TemporaryDirectory(prefix=".character-r7-", dir=destination) as temp:
        stage = Path(temp)
        atlas.save(stage / "atlas.png", format="PNG")
        for name, source in portraits.items():
            shutil.copyfile(source, stage / name)
        (stage / "registry.json").write_text(
            json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        (stage / "character.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        for name in sorted([*portraits, "atlas.png", "registry.json", "character.json"]):
            os.replace(stage / name, destination / name)
    return registry


def main(argv=None):
    parser = argparse.ArgumentParser(description="DrawTemp R7 character recipe tool")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--template", choices=sorted(starter_library()), default="jeanne")
    parser.add_argument("--recipe", type=Path, help="Existing authoring JSON")
    parser.add_argument("--save-template", type=Path, help="Write an editable starter")
    parser.add_argument("--export", type=Path, help="Export portable runtime asset pack")
    parser.add_argument("--strict", action="store_true", help="Enforce Jeanne outfit gate")
    args = parser.parse_args(argv)
    document = (json.loads(args.recipe.read_text(encoding="utf-8"))
                if args.recipe else starter_library()[args.template])
    validate(document)
    if args.save_template:
        args.save_template.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
    errors = diagnostics(document, require_outfits=args.strict)
    for issue in errors:
        print(json.dumps(issue, ensure_ascii=False))
    if args.export:
        export_pack(document, args.root, args.export, strict=args.strict)
        print("Exported:", args.export)
    return 1 if args.strict and any(row["severity"] == "error" for row in errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
