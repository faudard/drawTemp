"""Scalable, data-only character looks assembled from existing directional art.

No new illustrations or animations are implied. A look is one transaction
over a canonical R7 character variant (192x192), preserving the selected
character's authored idle/actions, other variants, and all gameplay data.
"""
from __future__ import annotations

from copy import deepcopy

from .character_parts import (
    PART_CATEGORIES, PROFILE_PARTS, PROFILE_PRESETS, PROFILE_TINTS,
    active_part, available_parts, part_paths, set_part,
)
from .characters import CharacterError, _check, validate

# All names refer to four-way families in assets/hero_parts. The list can
# grow or be loaded from a versioned look catalog; no UI hard-coded presets.
LOOKS = (
    ("male_villager", "Villager", "male", {"body": "classic", "front_hair": "tuft",
      "rear_hair": "bob", "top": "vest", "bottom": "trousers", "face": "friendly"}),
    ("male_knight", "Knight", "male", {"body": "rugged", "head_shape": "wide",
      "front_hair": "crest", "rear_hair": "bob", "top": "armor", "bottom": "trousers"}),
    ("male_ranger", "Ranger", "male", {"body": "slim", "front_hair": "tuft",
      "rear_hair": "long", "top": "poncho", "bottom": "trousers"}),
    ("male_mage", "Mage", "male", {"body": "tall", "front_hair": "long",
      "rear_hair": "long", "top": "hoodie", "bottom": "trousers"}),
    ("male_guard", "Guard", "male", {"body": "stout", "front_hair": "mohawk",
      "rear_hair": "bob", "top": "armor", "bottom": "trousers"}),
    ("female_villager", "Villager", "female", {"body": "slim", "front_hair": "bob",
      "rear_hair": "braids", "top": "vest", "bottom": "kilt"}),
    ("female_knight", "Knight", "female", {"body": "curvy", "front_hair": "tuft",
      "rear_hair": "braids", "top": "armor", "bottom": "trousers"}),
    ("female_ranger", "Ranger", "female", {"body": "slim", "front_hair": "bob",
      "rear_hair": "long", "top": "poncho", "bottom": "trousers"}),
    ("female_mage", "Mage", "female", {"body": "tall", "front_hair": "long",
      "rear_hair": "long", "top": "hoodie", "bottom": "kilt"}),
    ("female_guard", "Guard", "female", {"body": "classic", "front_hair": "crest",
      "rear_hair": "bob", "top": "armor", "bottom": "trousers"}),
    ("kid_villager", "Villager", "kid", {"body": "slim", "front_hair": "tuft",
      "rear_hair": "bob", "top": "hoodie", "bottom": "shorts"}),
    ("kid_apprentice", "Apprentice", "kid", {"body": "slim", "front_hair": "bob",
      "rear_hair": "long", "top": "vest", "bottom": "shorts"}),
    ("kid_scout", "Scout", "kid", {"body": "slim", "front_hair": "crest",
      "rear_hair": "bob", "top": "poncho", "bottom": "shorts"}),
    ("kid_mage", "Mage", "kid", {"body": "slim", "front_hair": "long",
      "rear_hair": "long", "top": "hoodie", "bottom": "shorts"}),
    ("kid_traveller", "Traveller", "kid", {"body": "slim", "front_hair": "bob",
      "rear_hair": "braids", "top": "poncho", "bottom": "shorts"}),
)
LOOK_BY_ID = {entry[0]: entry for entry in LOOKS}
# Suggested positions, applied at creation; users may freely override them.
# Coordinates are pixels relative to the 192x192 character canvas.
DEFAULT_OFFSETS = {
    "rear_hair": [0, 0], "front_hair": [0, 0],
    "head_shape": [0, 0], "top": [0, 0], "bottom": [0, 0],
}


def available_looks(profile=None):
    """Stable search/display data. No Qt, images or external reads."""
    _check(profile is None or profile in PROFILE_PRESETS, "Unknown profile")
    return tuple({"id": key, "name": label, "profile": kind}
                 for key, label, kind, _ in LOOKS if profile in (None, kind))


def apply_look(document, variant_id, look_id, root):
    """One undoable appearance edit while preserving clips/expressions.

    Retains custom layers outside the curated look slots and leaves all other
    character variants intact. This operation never copies another pose.
    """
    validate(document)
    _check(document.get("size") == [192, 192], "Looks require a 192x192 character")
    _check(variant_id in document["variants"], "Unknown character variant")
    _check(look_id in LOOK_BY_ID, "Unknown character look")
    _, _, profile, changes = LOOK_BY_ID[look_id]
    # Curated defaults; no restrictions on later edits or on any slot.
    specification = dict(PROFILE_PARTS[profile])
    specification.update(changes)
    for slot, _ in PART_CATEGORIES:
        if slot not in specification:
            continue
        name = specification[slot]
        _check(name in available_parts(root, slot),
               f"Missing look asset: {slot}/{name}")
        set_part(document, variant_id, slot, name, root)
        layer = active_part(document, variant_id, slot)
        layer["offset"] = list(DEFAULT_OFFSETS.get(slot, (0, 0)))
        layer["tint"] = PROFILE_TINTS[profile].get(slot, "#ffffff")
        layer["opacity"] = 255
    # Newly inserted slots are sorted by painter order, without changing
    # custom animation frames, identity, name, or other variants.
