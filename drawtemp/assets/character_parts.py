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
    ("body", "Body"), ("rear_hair", "Rear Hair"),
    ("head_shape", "Head shape"),
    ("ears", "Ears"), ("skin_spots", "Skin spots"),
    ("head_pattern", "Head pattern"), ("face", "Face"),
    ("eyes", "Eyes"), ("iris", "Iris"), ("pupil", "Pupil"),
    ("brows", "Eyebrows"), ("nose", "Nose"), ("mouth", "Mouth"),
    ("teeth", "Teeth"), ("facial_hair", "Facial hair"),
    ("front_hair", "Front Hair"), ("hair", "Hair (Legacy)"),
    ("cap", "Headwear"), ("horns", "Horns"),
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
SPLIT_HAIR_SLOTS = frozenset(("front_hair", "rear_hair"))
ORDER = {slot: index for index, (slot, _) in enumerate(PART_CATEGORIES)}


def _folder(root, slot):
    if slot not in PART_NAMES:
        raise CharacterError("Unknown modular part: " + str(slot))
    base = Path(root).resolve()
    folder = (base / PART_ROOT / slot).resolve()
    _check(folder.is_relative_to(base) and folder.is_dir(),
           "Missing or unsafe part category: " + slot)
    return folder


def _family_names(folder):
    """Discover complete PNG families; incomplete authored sets are never selectable."""
    if not folder.is_dir():
        return set()
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
    return names


def available_parts(root, slot):
    """Find authored front/rear components, falling back to legacy hairstyles.

    A future set of independently painted PNGs in front_hair/ or rear_hair/
    takes precedence over the original hair/ images. Until those artworks
    exist, each category offers the original directions with a conservative
    authoring-time front/rear separation (see split_legacy_hair_front).
    """
    folder = _folder(root, slot)
    names = _family_names(folder)
    if slot in SPLIT_HAIR_SLOTS:
        names.update(_family_names(_folder(root, "hair")))
    return tuple(sorted(names))


def part_paths(slot, name, root=None):
    """Select complete authored four-way art, or legacy hair as fallback."""
    if slot not in PART_NAMES or not name or not name.replace("_", "").isalnum():
        raise CharacterError("Invalid modular part")
    source_slot = slot
    if slot in SPLIT_HAIR_SLOTS:
        repository = (Path(root) if root is not None
                      else Path(__file__).resolve().parents[2]).resolve()
        folder = repository / PART_ROOT / slot
        if name not in _family_names(folder):
            source_slot = "hair"
    return {
        direction: (PART_ROOT / source_slot /
                    f"{name}_{suffix}.png").as_posix()
        for direction, suffix in DIRECTION_SUFFIXES.items()
    }


def split_legacy_hair_front(source):
    """Make a front fringe from existing full-hair artwork (Pillow RGBA).

    Preserve the upper 55% of the occupied alpha bounding box. The full
    legacy hair shape is used behind the head for Rear Hair; a newly
    authored front_hair PNG is rendered without this approximation.
    The original PNG is never modified.
    """
    alpha = source.getchannel("A")
    box = alpha.getbbox()
    if box is None:
        return source
    left, top, right, bottom = box
    cutoff = min(bottom, top + max(1, round((bottom - top) * 0.55)))
    if cutoff >= source.height:
        return source
    clipped = source.copy()
    clipped.paste((0, 0, 0, 0), (0, cutoff, source.width, source.height))
    return clipped


def upgrade_legacy_hair(document, variant_id, root):
    """Explicit, undoable conversion of legacy hair into two editable slots.

    Keep the original recipe unchanged until invoked. Preserve tint, opacity
    and position, and do not overwrite any user-authored front/rear layers.
    """
    validate(document)
    _check(variant_id in document["variants"], "Unknown outfit")
    _check(document["size"] == [192, 192],
           "Legacy split is supported only for modular 192x192 characters")
    layers = document["variants"][variant_id]["layers"]
    old = next((layer for layer in layers if layer["slot"] == "hair"), None)
    _check(old is not None, "No legacy hairstyle in selected outfit")
    name = None
    south = old["paths"].get("south", "")
    if south.startswith("assets/hero_parts/hair/") and south.endswith("_front.png"):
        name = Path(south).stem[:-len("_front")]
    _check(name is not None and name in available_parts(root, "front_hair"),
           "Only bundled legacy hairstyles can be split automatically")
    import copy
    for slot in ("rear_hair", "front_hair"):
        if active_part(document, variant_id, slot) is None:
            set_part(document, variant_id, slot, name, root)
            layer = active_part(document, variant_id, slot)
            layer["tint"] = old["tint"]
            layer["opacity"] = old["opacity"]
            layer["offset"] = copy.deepcopy(old["offset"])
    layers.remove(old)


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
        old["paths"] = part_paths(slot, name, root)
    else:
        new = {"slot": slot, "paths": part_paths(slot, name, root),
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
        "mouth": "neutral", "front_hair": "tuft", "rear_hair": "bob",
        "facial_hair": "moustache",
        "bottom": "trousers", "top": "vest",
    },
    "female": {
        "body": "slim", "head_shape": "round", "ears": "round",
        "face": "friendly", "eyes": "big", "iris": "large",
        "pupil": "round", "brows": "arched", "nose": "tiny",
        "mouth": "smile", "front_hair": "bob", "rear_hair": "braids",
        "bottom": "kilt", "top": "poncho",
    },
    "kid": {
        "body": "slim", "head_shape": "round", "ears": "round",
        "skin_spots": "freckles", "face": "friendly", "eyes": "cute",
        "iris": "large", "pupil": "round", "brows": "soft",
        "nose": "button", "mouth": "grin",
        "front_hair": "tuft", "rear_hair": "bob",
        "bottom": "shorts", "top": "hoodie",
    },
}
PROFILE_TINTS = {
    "male": {"front_hair": "#c99c73", "rear_hair": "#c99c73",
             "top": "#7aa9c5"},
    "female": {"front_hair": "#c69a65", "rear_hair": "#c69a65",
               "top": "#b9a5e2"},
    "kid": {"front_hair": "#e4ba76", "rear_hair": "#e4ba76",
            "top": "#87cdb5"},
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
