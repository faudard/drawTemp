"""Build a reproducible, non-destructive wolf animation kit from the existing artwork.

This expands *timing and secondary motion*, not missing hand-drawn anatomical
poses or camera directions. Output is isolated from the original watercolor pack.

Usage:
    python -m pip install Pillow
    python scripts/build_wolf_animation_kit.py
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SOURCE_NAMES = (
    "idle", "walk_a", "walk_b", "crouch", "pounce", "leap",
    "growl", "defend", "snarl", "hit", "ko", "howl",
)

# Each tuple is (original drawing, duration in milliseconds, x offset, y offset,
# scale). Frames are intentionally separate PNGs, so the registry works in
# consumers which support only ordinary sprites, not runtime interpolation.
CLIPS = {
    "idle": (True, [("idle", 170, 0, 0, 1), ("idle", 170, 0, -1, 1.006),
                    ("idle", 170, 0, -2, 1.012), ("idle", 170, 0, -1, 1.006)]),
    "walk": (True, [("walk_a", 115, -2, 0, .99), ("walk_a", 115, 0, -2, 1),
                    ("walk_b", 115, 2, 0, .99), ("walk_b", 115, 0, -2, 1),
                    ("walk_a", 115, -2, 0, .99), ("walk_b", 115, 2, -1, 1)]),
    "run": (True, [("crouch", 85, -3, 1, .98), ("walk_a", 85, 0, -4, 1.02),
                   ("leap", 85, 3, -5, 1.03), ("walk_b", 85, 2, -1, .99),
                   ("walk_a", 85, -2, -3, 1.02), ("walk_b", 85, 0, 0, .99)]),
    "alert": (True, [("idle", 180, 0, 0, 1), ("growl", 180, 0, -2, 1.01),
                     ("snarl", 180, 0, 0, 1), ("growl", 180, 0, -1, 1)]),
    "growl": (True, [("growl", 130, 0, 0, 1), ("snarl", 130, 0, -1, 1.01),
                     ("growl", 130, 0, 0, 1)]),
    "howl": (False, [("idle", 130, 0, 0, 1), ("growl", 150, 0, -2, 1),
                     ("howl", 180, 0, -3, 1.015), ("howl", 220, 0, -4, 1.02),
                     ("howl", 180, 0, -2, 1.01), ("idle", 140, 0, 0, 1)]),
    "bite": (False, [("idle", 95, 0, 0, 1), ("crouch", 90, -2, 2, .98),
                     ("snarl", 75, 2, -1, 1.03), ("pounce", 85, 5, -3, 1.04),
                     ("growl", 90, 2, -1, 1), ("idle", 120, 0, 0, 1)]),
    "pounce": (False, [("crouch", 110, -2, 2, .99), ("crouch", 100, -3, 3, .97),
                       ("pounce", 95, 0, -3, 1.02), ("leap", 95, 3, -7, 1.04),
                       ("leap", 105, 5, -5, 1.04), ("walk_a", 100, 2, 0, 1),
                       ("idle", 125, 0, 0, 1)]),
    "defend": (False, [("idle", 100, 0, 0, 1), ("defend", 125, -1, 0, 1),
                       ("defend", 170, 0, -1, 1.01), ("idle", 130, 0, 0, 1)]),
    "hit": (False, [("idle", 75, 0, 0, 1), ("hit", 110, -3, 1, .98),
                    ("hit", 110, -5, 2, .97), ("crouch", 130, -2, 1, .99),
                    ("idle", 140, 0, 0, 1)]),
    "death": (False, [("hit", 110, -3, 2, .98), ("crouch", 140, -2, 4, .96),
                      ("ko", 180, 0, 3, 1), ("ko", 400, 0, 3, 1)]),
    "dead": (False, [("ko", 500, 0, 0, 1)]),
}

def render_frame(source, dx, dy, scale):
    from PIL import Image
    w, h = source.size
    if not (.90 <= scale <= 1.10):
        raise ValueError("Unexpected scale")
    # Scale around the foot pivot, not around the centre of the sprite.
    sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
    image = source.resize((sw, sh), Image.Resampling.BICUBIC)
    canvas = Image.new("RGBA", (w, h))
    pivot_x, pivot_y = w // 2, round(h * .9)
    x = round(pivot_x - pivot_x * scale + dx)
    y = round(pivot_y - pivot_y * scale + dy)
    canvas.paste(image, (x, y), image)
    return canvas

def build(source_dir: Path, output_dir: Path):
    from PIL import Image
    missing = [name for name in SOURCE_NAMES if not (source_dir / (name + ".png")).is_file()]
    if missing:
        raise FileNotFoundError("Missing original wolf poses: " + ", ".join(missing))
    if source_dir.resolve() == output_dir.resolve():
        raise ValueError("Never overwrite the authored watercolor source poses")
    originals = {}
    for name in SOURCE_NAMES:
        with Image.open(source_dir / (name + ".png")) as image:
            originals[name] = image.convert("RGBA")
    if len({image.size for image in originals.values()}) != 1:
        raise ValueError("All wolf poses must share one stable canvas size")
    frame_dir = output_dir / "sprites" / "wolf"
    frame_dir.mkdir(parents=True, exist_ok=True)
    entries, animations = [], {}
    w, h = originals["idle"].size
    for clip_name, (loop, poses) in CLIPS.items():
        frames = []
        for index, (pose, duration, x, y, scale) in enumerate(poses):
            asset_id = f"wolf_v2_{clip_name}_{index:02d}"
            rel = f"sprites/wolf/{clip_name}_{index:02d}.png"
            render_frame(originals[pose], x, y, scale).save(output_dir / rel, optimize=True)
            entries.append({"id": asset_id, "kind": "sprite", "path": rel})
            frames.append({"sprite": asset_id, "duration_ms": duration})
        entry_id = "anim_wolf_v2_" + clip_name
        entries.append({"id": entry_id, "kind": "animation",
                        "loop": loop, "frames": frames})
        animations[clip_name] = entry_id
    registry = {"version": 1, "entries": entries, "bindings": {}}
    (output_dir / "registry.json").write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "kit.json").write_text(
        json.dumps({"id": "wolf_v2", "family": "bestiary", "view": "single",
                    "directions": ["source_view_only"], "canvas": [w, h],
                    "pivot": [w // 2, round(h * .9)],
                    "animations": animations, "frame_count": sum(len(p) for _, p in CLIPS.values()),
                    "source": "assets/watercolor/sprites/wolf",
                    "method": "reused poses with small rigid transforms",
                    "production_limitations": [
                        "Not true in-between character drawings or multi-direction art",
                        "Bite and run reuse existing poses; require animator review",
                        "Not automatically bound to the Player"]},
                   indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(entries), len(animations)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=Path("assets/watercolor/sprites/wolf"))
    parser.add_argument("--output", type=Path,
                        default=Path("assets/animation_kits/wolf"))
    args = parser.parse_args()
    entries, clips = build(args.source, args.output)
    print(f"Wolf: {clips} clips, {entries - clips} frames, {entries} registry entries")

if __name__ == "__main__":
    main()
