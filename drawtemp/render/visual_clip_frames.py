"""R19.B2: shared, read-only visual frame selection for committed action clips.

The game journal is owned by AnimationDirector/R1; this module only maps
verified presentation clips to R7 CharacterPack frames or existing R4 assets.
It has no Qt import, world clock, mutation, RNG, save or gameplay dependency.
"""
from __future__ import annotations

from math import isfinite

# Source event -> R7 pose, legacy R4 pose. Never equate a cast with an attack.
# Heal/miss/interrupt have effects but no invented character action.
POSES = {
    "move": ("walk", "move"),
    "attack": ("attack", "attack"),
    "cast": ("magic", None),
    "impact": ("hit", "hit"),
    "block": ("block", None),
}
DIRECTIONS = frozenset(("south", "north", "east", "west"))


def facing_for_clip(clip, actor=None):
    """Use logged displacement/target direction, otherwise the actor facing.

    Zero-distance damage/casting must not snap Jeanne to the south. No facing
    state is written back to the session or to the canonical scene.
    """
    if not isinstance(clip, dict):
        return "south"
    start, end = clip.get("start"), clip.get("end")
    if (isinstance(start, (tuple, list)) and isinstance(end, (tuple, list))
            and len(start) == len(end) == 2
            and all(type(n) in (int, float) and isfinite(n)
                    for n in (*start, *end))):
        dx, dy = end[0] - start[0], end[1] - start[1]
        if dx or dy:
            if abs(dx) > abs(dy):
                return "east" if dx > 0 else "west"
            return "south" if dy > 0 else "north"
    direction = actor.get("direction") if isinstance(actor, dict) else None
    return direction if direction in DIRECTIONS else "south"


def clip_art_frame(clip, phase, *, actor, character=None, variant=None, assets=None):
    """Resolve one R19 visual pose for a committed R12 clip.

    Return the normalized R4 image record or an empty dict. The R7 clip's
    *actual duration* is sampled through normalized QML phase so a 900 ms
    three-frame magic pose does not get stuck at its first frame when the
    committed visual budget is shorter. Timeline phase is cosmetic only.
    """
    if (not isinstance(clip, dict) or not isinstance(actor, dict)
            or clip.get("actor") != actor.get("id")
            or type(phase) not in (int, float) or not isfinite(phase)
            or not 0 <= phase <= 1):
        return {}
    mapping = POSES.get(clip.get("kind"))
    if mapping is None:
        return {}
    duration_ms = clip.get("duration_ms")
    if type(duration_ms) is not int or not 1 <= duration_ms <= 60000:
        return {}
    direction = facing_for_clip(clip, actor)
    r7_action, legacy_pose = mapping
    actor_id = actor["id"]

    if character is not None and getattr(character, "character_id", None) == actor_id:
        outfit = variant or character.variants[0]
        if outfit not in character.variants:
            return {}
        try:
            total = character.duration(outfit, r7_action, direction)
            if total:
                elapsed = min(total - 1, int(phase * total))
                frame = character.sample(
                    variant=outfit, action=r7_action, direction=direction,
                    elapsed_ms=elapsed)
                if frame and frame.get("spriteReady"):
                    rect, pivot = frame["spriteRegion"], frame["spritePivot"]
                    return {
                        "imageUrl": frame["spriteUrl"],
                        "atlasX": rect[0], "atlasY": rect[1],
                        "frameWidth": rect[2], "frameHeight": rect[3],
                        "pivotX": pivot[0], "pivotY": pivot[1],
                        "direction": direction, "pose": r7_action,
                        "source": "character_pack",
                    }
        except (OSError, KeyError, ValueError, TypeError):
            return {}
        # Don't silently turn an unavailable R7 magic/block into an R4
        # idle sprite. Old authored packs are allowed to remain incomplete.
        if legacy_pose is None:
            return {}

    if assets is not None and legacy_pose is not None:
        try:
            frame = assets.actor_frame(
                actor_id, direction=direction, pose=legacy_pose,
                elapsed_ms=min(duration_ms - 1, int(phase * duration_ms)))
            if frame and frame.get("imageUrl"):
                return {**frame, "direction": direction,
                        "pose": legacy_pose, "source": "project_assets"}
        except (OSError, ValueError, TypeError, RuntimeError):
            return {}
    return {}
