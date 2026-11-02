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


# Editable appearance presets. These are starting points, never restrictions
# on hair, clothing, or other choices. They use the SAME directional parts
# catalog and canonical recipe as all custom characters.
PROFILE_PRESETS = ("male", "female", "kid")
PROFILE_LABELS = {"male": "Male", "female": "Female", "kid": "Kid"}
PROFILE_PARTS = {
    "male": {
        "body": "classic", "head_shape": "wide", "ears": "round",
        "face": "determined", "eyes": "friendly", "iris": "round",
        "pupil": "round", "brows": "straight", "nose": "round",
        "mouth": "neutral", "hair": "tuft", "facial_hair": "moustache",
        "bottom": "trousers", "top": "vest",
    },
    "female": {
        "body": "slim", "head_shape": "round", "ears": "round",
        "face": "friendly", "eyes": "big", "iris": "large",
        "pupil": "round", "brows": "arched", "nose": "tiny",
        "mouth": "smile", "hair": "braids",
        "bottom": "kilt", "top": "poncho",
    },
    "kid": {
        "body": "slim", "head_shape": "round", "ears": "round",
        "skin_spots": "freckles", "face": "friendly", "eyes": "cute",
        "iris": "large", "pupil": "round", "brows": "soft",
        "nose": "button", "mouth": "grin", "hair": "tuft",
        "bottom": "shorts", "top": "hoodie",
    },
}
PROFILE_TINTS = {
    "male": {"hair": "#c99c73", "top": "#7aa9c5"},
    "female": {"hair": "#c69a65", "top": "#b9a5e2"},
    "kid": {"hair": "#e4ba76", "top": "#87cdb5"},
}


def profile_variant(profile):
    """Author one ready-to-edit profile using the repository's actual parts.

    This is a static directional appearance. Animation frames other than idle
    are NOT synthesized from idle PNGs. Missing actions remain diagnosed.
    """
    from .characters import frame
    _check(profile in PROFILE_PRESETS, "Unknown character profile: " + str(profile))
    layers = [{
        "slot": slot,
        "paths": part_paths(slot, name),
        "offset": [0, 0],
        "tint": PROFILE_TINTS[profile].get(slot, "#ffffff"),
        "opacity": 255,
    } for slot, _ in PART_CATEGORIES
      if (name := PROFILE_PARTS[profile].get(slot)) is not None]
    # A genuine, authored fully-transparent image, rather than painted fakes.
    idle = {direction: [frame(
        (PART_ROOT / "accessory" /
         f"none_{DIRECTION_SUFFIXES[direction]}.png").as_posix())]
        for direction in DIRECTIONS}
    return {
        "name": PROFILE_LABELS[profile],
        "expressions": {},
        "clips": {"idle": {"loop": True, "directions": idle}},
        "layers": layers,
    }


def ensure_profile(document, profile):
    """Create a missing profile without touching existing outfits or sprites.

    Allows opening an earlier Modular Hero JSON that only had 'default':
    switching to a profile adds an independent, undoable variation.
    """
    _check(document.get("id") == "modular_hero" and
           document.get("size") == [192, 192],
           "Profiles are available on the Modular Hero 192x192 template")
    _check(profile in PROFILE_PRESETS, "Unknown character profile")
    if profile not in document["variants"]:
        _check(len(document["variants"]) < 32, "Too many character variants")
        document["variants"][profile] = profile_variant(profile)


def modular_starter():
    """Three independent appearance profiles, one compatible Recipe v1."""
    return validate({
        "version": 1, "id": "modular_hero", "name": "Modular Hero",
        "size": [192, 192], "pivot": [96, 191],
        "variants": {key: profile_variant(key) for key in PROFILE_PRESETS},
    })
