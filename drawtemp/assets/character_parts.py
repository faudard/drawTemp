"""Visual modular parts for the R7 Character Studio.

Uses existing directional hero PNGs. No new runtime format or game state;
all edits remain Character Recipe v1 layers and use R7 export/render_frame.
"""
from __future__ import annotations

from pathlib import Path

from .characters import CharacterError, DIRECTIONS, _check, validate

PART_ROOT = Path("assets/hero_parts")
# In painter order (back to front). These folders are pre-existing authored art.
PART_CATEGORIES = (
    ("body", "Body"), ("head_shape", "Head shape"),
    ("ears", "Ears"), ("skin_spots", "Skin spots"),
    ("head_pattern", "Head pattern"), ("face", "Face"),
    ("eyes", "Eyes"), ("iris", "Iris"), ("pupil", "Pupil"),
    ("brows", "Eyebrows"), ("nose", "Nose"), ("mouth", "Mouth"),
    ("teeth", "Teeth"), ("facial_hair", "Facial hair"),
    ("hair", "Hair"), ("cap", "Headwear"), ("horns", "Horns"),
    ("bottom", "Bottom"), ("top", "Clothing"),
    ("mark", "Mark 1"), ("mark_2", "Mark 2"),
    ("mark_3", "Mark 3"), ("earrings", "Earrings"),
    ("jewelry", "Jewelry"), ("accessory", "Accessory 1"),
    ("accessory_2", "Accessory 2"), ("accessory_3", "Accessory 3"),
    ("weapon", "Weapon"),
)
DIRECTION_SUFFIXES = {
    "south": "front", "north": "back", "east": "right", "west": "left",
}
PART_NAMES = frozenset(slot for slot, _ in PART_CATEGORIES)
ORDER = {slot: index for index, (slot, _) in enumerate(PART_CATEGORIES)}


def _folder(root, slot):
    if slot not in PART_NAMES:
        raise CharacterError("Unknown modular part: " + str(slot))
    base = Path(root).resolve()
    folder = (base / PART_ROOT / slot).resolve()
    _check(folder.is_relative_to(base) and folder.is_dir(),
           "Missing or unsafe part category: " + slot)
    return folder


def available_parts(root, slot):
    """Only list genuine complete four-direction asset families."""
    folder = _folder(root, slot)
    names = set()
    for path in folder.glob("*_front.png"):
        stem = path.name[:-len("_front.png")]
        if not stem or not all(
            (folder / f"{stem}_{suffix}.png").is_file()
            and (folder / f"{stem}_{suffix}.png").resolve().is_relative_to(folder)
            for suffix in DIRECTION_SUFFIXES.values()
        ):
            continue
        names.add(stem)
    return tuple(sorted(names))


def part_paths(slot, name):
    """Canonical repository-relative paths for existing directional sprites."""
    if slot not in PART_NAMES or not name or not name.replace("_", "").isalnum():
        raise CharacterError("Invalid modular part")
    return {
        direction: (PART_ROOT / slot / f"{name}_{suffix}.png").as_posix()
        for direction, suffix in DIRECTION_SUFFIXES.items()
    }


def active_part(document, variant_id, slot):
    return next((layer for layer in document["variants"][variant_id]["layers"]
                 if layer["slot"] == slot), None)


def set_part(document, variant_id, slot, name, root):
    """Mutate a session candidate; preserve tint/alpha/offset on replacement.

    Removal is done with name=None. Reject external or incomplete parts and
    canvas-size mismatches before touching the candidate.
    """
    validate(document)
    _check(variant_id in document["variants"], "Unknown outfit")
    _check(slot in PART_NAMES, "Unknown modular category")
    layers = document["variants"][variant_id]["layers"]
    old = active_part(document, variant_id, slot)
    if name is None:
        if old is not None:
            layers.remove(old)
        return
    _check(document["size"] == [192, 192],
           "Modular parts require a 192 x 192 canvas; select Modular Hero")
    _check(name in available_parts(root, slot), "Part variant not found: " + str(name))
    if old is not None:
        old["paths"] = part_paths(slot, name)
    else:
        new = {"slot": slot, "paths": part_paths(slot, name),
               "offset": [0, 0], "tint": "#ffffff", "opacity": 255}
        # Preserve legacy/art-directed order of other layers.
        index = next((i for i, layer in enumerate(layers)
                      if ORDER.get(layer["slot"], len(ORDER)) > ORDER[slot]),
                     len(layers))
        layers.insert(index, new)


def set_part_style(document, variant_id, slot, *, offset=None,
                   tint=None, opacity=None):
    """Edit only one modular layer (all four directions), with R7 validation."""
    validate(document)
    _check(variant_id in document["variants"], "Unknown outfit")
    _check(slot in PART_NAMES, "Unknown modular category")
    layer = active_part(document, variant_id, slot)
    _check(layer is not None, "Choose a part variation before editing its style")
    if offset is not None:
        layer["offset"] = list(offset)
    if tint is not None:
        layer["tint"] = tint
    if opacity is not None:
        layer["opacity"] = opacity
    # The caller's CharacterSession.edit validates atomically after mutation.


def modular_starter():
    """A transparent authoring base plus an existing four-way body asset.

    Do NOT synthesize 'walk' or 'attack' by duplicating idle artwork.
    Those clips can be authored using the existing R7 animation timeline.
    """
    from .characters import frame
    return validate({
        "version": 1, "id": "modular_hero", "name": "Modular Hero",
        "size": [192, 192], "pivot": [96, 191],
        "variants": {"default": {
            "name": "Default", "expressions": {},
            "clips": {"idle": {"loop": True, "directions": {
                direction: [frame(
                    (PART_ROOT / "accessory" /
                     f"none_{DIRECTION_SUFFIXES[direction]}.png").as_posix())]
                for direction in DIRECTIONS}}},
            "layers": [{
                "slot": "body", "paths": part_paths("body", "classic"),
                "offset": [0, 0], "tint": "#ffffff", "opacity": 255,
            }],
        }},
    })
