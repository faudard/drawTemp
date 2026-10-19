"""R19.B1: editable directional motion sketches for Jeanne in the R7 asset pipeline.

This creates distinctly posed candidate PNGs for six missing/underanimated
actions. Derived art is NOT licensed or artist-approved. No runtime rule,
CT, replay, GameProject schema or save file changes.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import tempfile

from .characters import DIRECTIONS, CharacterError, frame, export_pack, validate
from .jeanne_art import build_jeanne_art, OUTFITS

CELL = 64
SOURCE_SIZE = (4 * CELL, 8 * CELL)
# R7 row index, phase choices, milliseconds per frame, loop.
MOTION = {
    "run": (2, (0, 1, 2), (95, 95, 105), True),
    "magic": (0, (0, 1, 2), (175, 205, 250), False),
    "block": (4, (0, 1, 2), (135, 220, 260), False),
    "hit": (6, (0, 1), (135, 200), False),
    "death": (7, (0, 1), (165, 430), False),
    "victory": (1, (0, 1, 2), (190, 210, 380), False),
}


def _pose(base, action, direction, phase):
    """Draw new silhouette-changing gestures onto a copy of a source keyframe.

    These frames are artist-editable prototypes, not replacements for final,
    hand-reviewed pose-by-pose commissioned production artwork.
    """
    from PIL import Image, ImageDraw

    if action == "death":
        # A real collapsed silhouette, rather than the standing defeat icon.
        if phase:
            base = base.rotate(60 if direction in ("south", "west") else -60,
                               resample=Image.Resampling.BICUBIC, center=(32, 52))
    elif action == "hit":
        # Two distinct recoil poses, with the feet remaining within the tile.
        shift = -2 if phase == 0 else 3
        pose = Image.new("RGBA", (CELL, CELL))
        pose.alpha_composite(base, (shift, -1 if phase == 0 else 0))
        base = pose
    elif action == "run":
        # Translate the body, then extend opposite arms/boots per phase.
        shift = (-2, 0, 2)[phase]
        pose = Image.new("RGBA", (CELL, CELL))
        pose.alpha_composite(base, (shift, -2 if phase == 1 else 0))
        base = pose

    paint = ImageDraw.Draw(base, "RGBA")
    sign = -1 if direction in ("north", "west") else 1
    left, right = (24, 40) if sign == 1 else (40, 24)
    steel = (94, 118, 148, 255)
    leather = (105, 74, 57, 255)
    linen = (225, 208, 171, 255)
    gold = (230, 188, 100, 255)

    if action == "run":
        stride = (-7, 0, 7)[phase] * sign
        # Distinct gait silhouette, opposing sleeves, boot placements and dust.
        paint.polygon([(25 + stride, 52), (31 + stride, 51),
                       (32 + stride, 61), (23 + stride, 62)], fill=leather)
        paint.polygon([(35 - stride, 53), (41 - stride, 52),
                       (43 - stride, 61), (33 - stride, 62)], fill=(67, 58, 55, 255))
        paint.line([(left, 31), (left - sign * (4 + phase * 2), 42 - phase * 3)],
                   fill=linen, width=4)
        paint.line([(right, 30), (right + sign * (5 + (2 - phase) * 2), 40)],
                   fill=leather, width=4)
        paint.ellipse((15 + 2 * phase, 59, 21 + 2 * phase, 62),
                      fill=(154, 126, 100, 110))
    elif action == "magic":
        reach = (4, 12, 19)[phase]
        # Arms and spellcasting pose are visible beyond garment edges.
        paint.line([(left, 32), (left - reach * sign, 31 - reach)],
                   fill=steel, width=5)
        paint.ellipse((left - reach * sign - 3, 28 - reach,
                       left - reach * sign + 3, 34 - reach), fill=linen)
        paint.line([(right, 32), (right + reach * sign, 36 - reach)],
                   fill=steel, width=4)
        cx, cy = 31 + (reach - 4) * sign, 19 - phase * 4
        paint.arc((cx - 7, cy - 7, cx + 7, cy + 7),
                  35 + phase * 20, 300 - phase * 12,
                  fill=(114, 211, 239, 255), width=2 + phase)
        paint.line([(cx - 8, cy), (cx + 8, cy)],
                   fill=(216, 237, 236, 235), width=2)
        paint.ellipse((cx - 2 - phase, cy - 2 - phase,
                       cx + 2 + phase, cy + 2 + phase),
                      fill=(229, 247, 249, 255))
    elif action == "block":
        # A raised/angled shield enlarges the silhouette rather than recoloring
        # the existing attack row. Three phases: ready, intercept and hold.
        px = (14, 10, 12)[phase] if sign == 1 else (37, 41, 39)[phase]
        y = (25, 18, 21)[phase]
        paint.line([(left, 31), (px + 8, y + 11)], fill=leather, width=6)
        paint.polygon([(px, y), (px + 16, y + 1),
                       (px + 17, y + 18), (px + 8, y + 25),
                       (px - 1, y + 18)], fill=steel)
        paint.line([(px + 1, y + 3), (px + 15, y + 4),
                    (px + 15, y + 17), (px + 8, y + 22)],
                   fill=gold, width=2)
        paint.line([(px + 8, y + 4), (px + 8, y + 19)],
                   fill=linen, width=2)
    elif action == "hit":
        px = 28 + sign * (5 if phase else 0)
        paint.line([(px - 5, 33), (px + 6, 39 - 3 * phase)],
                   fill=(170, 68, 72, 255), width=3)
        paint.line([(px + 4, 32), (px - 3, 41 - 3 * phase)],
                   fill=linen, width=2)
    elif action == "death":
        if phase == 0:
            paint.line([(18, 44), (43, 48)], fill=(136, 76, 79, 255), width=2)
        else:
            # Restrained settling / dust effect, with no changes to gameplay LOS.
            paint.ellipse((10, 58, 54, 63), fill=(79, 65, 62, 130))
            paint.line([(21, 57), (45, 60)], fill=(130, 101, 86, 220), width=2)
    elif action == "victory":
        # Flagpole and differently rippling banner; fully inside 64 px canvas.
        px = 17 if sign == 1 else 47
        pole_bottom = 44 - phase * 5
        paint.line([(left, 29), (px, pole_bottom)], fill=linen, width=4)
        paint.line([(px, pole_bottom), (px, 7 - phase * 2)],
                   fill=leather, width=3)
        turn = (5, 11, 7)[phase] * sign
        paint.polygon([(px + sign * 2, 9 - phase * 2),
                       (px + turn + sign * 8, 12),
                       (px + turn, 23 + phase * 2),
                       (px + sign * 2, 19)],
                      fill=(75, 111, 162, 255))
        paint.line([(px + sign * 2, 9 - phase * 2),
                    (px + turn + sign * 8, 12)], fill=gold, width=2)
        paint.ellipse((27 + phase, 16, 30 + phase, 19), fill=gold)
    return base


def render_motion_strips(source):
    """Create 6 deterministic, four-direction strips from source RGBA artwork."""
    from PIL import Image

    source = Path(source)
    with Image.open(source) as handle:
        if handle.size != SOURCE_SIZE:
            raise CharacterError("Expected 256x512 Jeanne atlas (R7)")
        original = handle.convert("RGBA")
    strips = {}
    for action, (row, phases, _, _) in MOTION.items():
        canvas = Image.new("RGBA", (CELL * len(DIRECTIONS), CELL * len(phases)))
        for col, direction in enumerate(DIRECTIONS):
            for index, phase in enumerate(phases):
                base = original.crop((col * CELL, row * CELL,
                                      (col + 1) * CELL, (row + 1) * CELL))
                # For run, alternate source gait; visual phase still authored.
                if action == "run" and phase == 1:
                    base = original.crop((col * CELL, 3 * CELL,
                                          (col + 1) * CELL, 4 * CELL))
                drawn = _pose(base, action, direction, phase)
                canvas.alpha_composite(drawn, (col * CELL, index * CELL))
        strips[action] = canvas
    return strips


def motion_recipe(recipe):
    """Extend an R7 v1 recipe, without adding schema fields or gameplay data."""
    edited = validate(recipe)
    for outfit in edited["variants"].values():
        for action, (_, phases, timings, loop) in MOTION.items():
            directions = {}
            for col, direction in enumerate(DIRECTIONS):
                directions[direction] = [
                    frame(f"sources/jeanne_r19_{action}.png",
                          region=[col * CELL, index * CELL, CELL, CELL],
                          duration_ms=timings[index])
                    for index in range(len(phases))
                ]
            outfit["clips"][action] = {"loop": loop, "directions": directions}
    return validate(edited)


def _png_bytes(image):
    from io import BytesIO
    stream = BytesIO()
    image.save(stream, format="PNG", optimize=True)
    return stream.getvalue()


def _snapshot(folder):
    """A digest inventory, including symlink refusal, to preserve artist edits."""
    files = {}
    for path in Path(folder).rglob("*"):
        if path.is_symlink():
            raise CharacterError("Symlinks are not valid in an authored kit")
        if path.is_file():
            files[path.relative_to(folder).as_posix()] = sha256(path.read_bytes()).hexdigest()
    return files


def build_jeanne_motion(repository, destination):
    """Generate a self-contained R19 candidate pack; fail closed on edited files.

    Uses the R7 compositor/AssetRegistry unchanged, publishes a new directory
    atomically, and does not modify an existing R7 source pack in place.
    """
    repository = Path(repository).resolve(strict=True)
    destination = Path(destination).resolve()
    if destination == repository or repository.is_relative_to(destination):
        raise CharacterError("Refusing to overwrite the repository")
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise CharacterError("Existing output path is not a regular directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".r19-motion-", dir=destination.parent) as temp:
        stage = Path(temp) / "candidate"
        base = build_jeanne_art(repository, stage)
        strips = render_motion_strips(stage / "sources/jeanne_atlas.png")
        derived = {}
        for action, image in sorted(strips.items()):
            relative = f"sources/jeanne_r19_{action}.png"
            payload = _png_bytes(image)
            (stage / relative).write_bytes(payload)
            derived[relative] = sha256(payload).hexdigest()
        upgraded = motion_recipe(base)
        (stage / "jeanne.character.json").write_text(
            json.dumps(upgraded, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        export_pack(upgraded, stage, stage / "runtime", strict=True)
        (stage / "r19-motion-provenance.json").write_text(
            json.dumps({
                "version": 1,
                "kind": "derived_motion_candidate",
                "source_atlas_sha256": sha256(
                    (stage / "sources/jeanne_atlas.png").read_bytes()).hexdigest(),
                "derived_sha256": derived,
                "redistribution_approved": False,
                "art_review": "pending",
                "note": "Prototype gestures; independently hand-reviewed art is still required",
            }, indent=2) + "\n", encoding="utf-8")
        if destination.exists():
            if _snapshot(destination) != _snapshot(stage):
                raise CharacterError("Existing authored R19 kit differs; not overwriting edits")
        else:
            stage.rename(destination)
    return upgraded


def main(argv=None):
    parser = argparse.ArgumentParser(description="R19.B1 Jeanne directional motion candidate")
    parser.add_argument("--repository", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    recipe = build_jeanne_motion(args.repository, args.output)
    print(json.dumps({"status": "candidate_not_artist_approved",
                      "output": str(args.output.resolve()),
                      "character": recipe["id"],
                      "outfits": sorted(recipe["variants"]),
                      "new_actions": sorted(MOTION)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
