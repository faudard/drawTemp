"""Artist-first PNG import for the R7 Character Studio.

Accept genuinely separate transparent four-direction artwork, not cropped
concept sheets or duplicated single images passed off as animations.
Preserve original high-resolution PNGs and generate a reusable character
recipe with a clear reference/idle distinction.

No PySide6 import: this also runs headlessly in CI.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from .characters import CharacterError, DIRECTIONS, frame, validate
from .character_parts import PART_NAMES

FACING_SUFFIXES = {
    "south": "front", "east": "right",
    "north": "back", "west": "left",
}
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
ART_ROOT = Path("assets/character_art")
PART_ROOT = Path("assets/hero_parts")


def _identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise CharacterError("Use a lowercase character/part ID: letters, digits, underscore")
    return value


def _read_png(path, *, transparent=True, maximum=2048):
    from PIL import Image, UnidentifiedImageError
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.suffix.lower() != ".png":
        raise CharacterError("Expected a genuine PNG file: " + str(path))
    try:
        with Image.open(path) as src:
            if src.format != "PNG":
                raise CharacterError("File is not actually a PNG: " + str(path))
            if not (32 <= src.width <= maximum and 32 <= src.height <= maximum):
                raise CharacterError("PNG dimensions outside 32–" +
                                     str(maximum) + ": " + str(path))
            has_alpha = "A" in src.getbands() or "transparency" in src.info
            if transparent and not has_alpha:
                raise CharacterError("Transparent RGBA artwork required: " + path.name)
            rgba = src.convert("RGBA")
            alpha = rgba.getchannel("A")
            extrema = alpha.getextrema()
            if transparent and (extrema[0] == 255 or extrema[1] == 0):
                raise CharacterError(
                    "Sprite must have visible artwork AND a transparent background: "
                    + path.name)
            return rgba
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        if isinstance(exc, CharacterError):
            raise
        raise CharacterError("Cannot read PNG " + str(path) + ": " + str(exc)) from exc


def _directional_sources(folder):
    """Reject incomplete, mixed-resolution and copied facing sets."""
    folder = Path(folder).resolve()
    sprites = {direction: _read_png(folder / (suffix + ".png"))
               for direction, suffix in FACING_SUFFIXES.items()}
    dims = {im.size for im in sprites.values()}
    if len(dims) != 1:
        raise CharacterError("All 4 directional PNGs must share identical dimensions")
    fingerprints = {hashlib.sha256(im.tobytes()).digest()
                    for im in sprites.values()}
    if len(fingerprints) < 3:
        raise CharacterError("Use real directional artwork; duplicated images are not accepted")
    return sprites


def _align_png(image, *, align_feet):
    """Keep source pixels intact: reposition alpha bbox without up/downscaling."""
    if not align_feet:
        return image.copy(), (0, 0)
    bounds = image.getchannel("A").getbbox()
    if not bounds:
        raise CharacterError("Empty sprite")
    x0, y0, x1, y1 = bounds
    cropped = image.crop(bounds)
    width, height = image.size
    x = (width - cropped.width) // 2
    y = max(0, height - 4 - cropped.height)
    aligned = image.__class__.new("RGBA", image.size, (0, 0, 0, 0))
    aligned.alpha_composite(cropped, (x, y))
    return aligned, (x - x0, y - y0)


def _write_png(image, path):
    image.save(path, format="PNG", optimize=True)


def build_character_recipe(identifier, label, canvas_size):
    """Portable v1 character with only *real* idle artwork and no fake walk."""
    _identifier(identifier)
    width, height = canvas_size
    source = ART_ROOT / identifier / "idle"
    variants = {
        "default": {
            "name": "Original Art",
            "expressions": {},
            "layers": [],
            "clips": {"idle": {
                "loop": True,
                "directions": {
                    direction: [frame((source / (suffix + ".png")).as_posix())]
                    for direction, suffix in FACING_SUFFIXES.items()
                },
            }},
        },
    }
    return validate({
        "version": 1, "id": identifier, "name": label,
        "size": [width, height], "pivot": [width // 2, height - 1],
        "variants": variants,
    })


def import_character_art(root, folder, identifier, label=None, *, align_feet=True):
    """Register a genuine 4-view full-art character, never overwrite sources.

    Input: front.png / right.png / back.png / left.png and optional
    portrait.png / reference.png. Output: assets/character_art/<id>/ with
    original sources, baseline-aligned idle sprites, and optional preview art;
    characters/<id>.character.json, discoverable by the character library.
    """
    root = Path(root).resolve()
    folder = Path(folder).resolve()
    identifier = _identifier(identifier)
    label = label or identifier.replace("_", " ").title()
    if not isinstance(label, str) or not label.strip():
        raise CharacterError("Character display name required")
    sprites = _directional_sources(folder)
    canvas = next(iter(sprites.values())).size
    portrait = folder / "portrait.png"
    reference = folder / "reference.png"
    optional = {}
    if portrait.is_file():
        optional["portrait.png"] = _read_png(
            portrait, transparent=False, maximum=4096)
    if reference.is_file():
        optional["reference.png"] = _read_png(
            reference, transparent=False, maximum=4096)
    destination = root / ART_ROOT / identifier
    recipe_path = root / "characters" / (identifier + ".character.json")
    if destination.exists() or recipe_path.exists():
        raise CharacterError("Character ID already exists: " + identifier)
    doc = build_character_recipe(identifier, label.strip(), canvas)
    if "portrait.png" in optional:
        doc["variants"]["default"]["expressions"]["portrait"] = (
            ART_ROOT / identifier / "portrait.png").as_posix()
    validate(doc)
    destination.parent.mkdir(parents=True, exist_ok=True)
    recipe_path.parent.mkdir(parents=True, exist_ok=True)
    offsets = {}
    with tempfile.TemporaryDirectory(prefix=".art-import-", dir=destination.parent) as tmp:
        stage = Path(tmp) / identifier
        (stage / "source").mkdir(parents=True)
        (stage / "idle").mkdir()
        for direction, suffix in FACING_SUFFIXES.items():
            src = folder / (suffix + ".png")
            shutil.copyfile(src, stage / "source" / (suffix + ".png"))
            aligned, offset = _align_png(sprites[direction], align_feet=align_feet)
            _write_png(aligned, stage / "idle" / (suffix + ".png"))
            offsets[direction] = list(offset)
        for name, image in optional.items():
            shutil.copyfile(folder / name, stage / name)
        (stage / "import.json").write_text(json.dumps({
            "version": 1, "type": "full_art", "id": identifier,
            "canvas": list(canvas), "align_feet": align_feet,
            "default_offsets": offsets,
            "status": "4 directional idle stills; animations NOT authored",
            "reference_only": "reference.png" in optional,
        }, indent=2) + "\n", encoding="utf-8")
        # A folder rename is atomic on the same volume.
        if destination.exists() or recipe_path.exists():
            raise CharacterError("Character ID already exists: " + identifier)
        stage.rename(destination)
    try:
        # Exclusive create avoids silently overwriting previously saved art.
        with recipe_path.open("x", encoding="utf-8") as output:
            json.dump(doc, output, indent=2, ensure_ascii=False)
            output.write("\n")
    except Exception:
        shutil.rmtree(destination)
        if recipe_path.exists():
            recipe_path.unlink()
        raise
    return doc, recipe_path


def import_part_set(root, folder, slot, part_id, *, align_feet=False):
    """Register four independent transparent 192x192 modular PNGs.

    The same importer serves 2D hand-painted layers: Front Hair, Rear Hair,
    clothing, face, accessories etc. Existing assets are never replaced.
    """
    root = Path(root).resolve()
    if slot not in PART_NAMES:
        raise CharacterError("Unknown modular category: " + str(slot))
    _identifier(part_id)
    sprites = _directional_sources(folder)
    if any(im.size != (192, 192) for im in sprites.values()):
        raise CharacterError("Modular parts must be 192x192 RGBA with common anchors")
    target = root / PART_ROOT / slot
    target.mkdir(parents=True, exist_ok=True)
    names = {suffix: target / (part_id + "_" + suffix + ".png")
             for suffix in FACING_SUFFIXES.values()}
    if any(path.exists() for path in names.values()):
        raise CharacterError("Modular variant already exists: " + slot + "/" + part_id)
    # All files validated before changes. Use an ephemeral staging directory
    # to avoid partially written PNGs if encoding fails.
    with tempfile.TemporaryDirectory(prefix=".part-import-", dir=target) as tmp:
        for direction, suffix in FACING_SUFFIXES.items():
            image, _ = _align_png(sprites[direction], align_feet=align_feet)
            _write_png(image, Path(tmp) / (part_id + "_" + suffix + ".png"))
        written = []
        try:
            for suffix, destination in names.items():
                if destination.exists():
                    raise CharacterError("Modular variant already exists")
                with destination.open("xb") as output:
                    output.write((Path(tmp) / (part_id + "_" + suffix + ".png")).read_bytes())
                written.append(destination)
        except Exception:
            for path in written:
                path.unlink(missing_ok=True)
            raise
    return tuple(names.values())


def import_reference_art(root, identifier, source):
    """Attach a concept sheet without claiming it is playable sprite art."""
    root = Path(root).resolve()
    _identifier(identifier)
    image = _read_png(source, transparent=False, maximum=4096)
    target = root / ART_ROOT / identifier
    target.mkdir(parents=True, exist_ok=True)
    path = target / "reference.png"
    # Explicit replacement of a non-runtime concept file only.
    staged = target / ".reference.tmp.png"
    _write_png(image, staged)
    staged.replace(path)
    return path


def reference_path(root, identifier):
    if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
        return None
    path = Path(root).resolve() / ART_ROOT / identifier / "reference.png"
    return path if path.is_file() else None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import artist-authored character PNGs")
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--folder", type=Path, required=True,
                        help="Folder with front/right/back/left transparent PNGs")
    parser.add_argument("--id", required=True, dest="identifier")
    parser.add_argument("--name")
    parser.add_argument("--keep-position", action="store_true",
                        help="Do not align foot baseline/center at import")
    args = parser.parse_args(argv)
    doc, target = import_character_art(
        args.root, args.folder, args.identifier, args.name,
        align_feet=not args.keep_position)
    print("Registered " + doc["name"] + ": " + str(target))


if __name__ == "__main__":
    main()
