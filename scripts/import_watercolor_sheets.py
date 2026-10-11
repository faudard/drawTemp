"""Import nine uploaded watercolor sheets into portable transparent sprites.

Authoring-only deps: pip install pillow numpy opencv-python-headless
Usage: python scripts/import_watercolor_sheets.py --input-dir SAMPLES --output-dir assets/watercolor
No runtime/Python engine dependency is introduced.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path

SHEETS = (
    ("vfx", "Planche de 16 effets de combat.png", 4, 4,
     "moon_small moon_large moon_break moon_dissolve spark_small spark_burst spark_fragments spark_dissolve dust_small dust_large dust_wide dust_dissolve arc_start arc_grow arc_complete arc_dissolve"),
    ("wolf", "Planche d’animation du loup gris.png", 4, 3,
     "idle walk_a walk_b crouch pounce leap growl defend snarl hit ko howl"),
    ("jeanne", "Jeanne : planche d’action en 12 poses.png", 4, 3,
     "idle walk_a walk_b ready windup slash followthrough guard hit kneel ko victory"),
    ("spearman", "Planche d’action : douze poses du lancier.png", 4, 3,
     "idle walk_a walk_b guard windup thrust recover ready block hit kneel ko"),
    ("props", "Douze objets médiévaux modulaires en aquarelle.png", 4, 3,
     "chapel forge market_stall camp_tent stone_bridge ruined_arch oak_tree pine_tree supply_cart palisade_gate stone_stairs treasure_chest"),
    ("townfolk", "Six personnages médiévaux en feuille d’assets.png", 3, 2,
     "scout blacksmith messenger royal_knight veteran_commander militia_axewoman"),
    ("soldiers", "Six soldats tactiques en aquarelle.png", 3, 2,
     "bandit spearman crossbowman royal_squire heavy_guard ranger"),
    ("bestiary", "Bestiaire médiéval fantastique en six créatures.png", 3, 2,
     "wolf boar bear gargoyle ogre spectral_hound"),
    ("heroes", "Six héros tactiques en aquarelle.png", 3, 2,
     "jeanne knight_captain healer nun red_knight english_champion"),
)
ANIMATIONS = {
    "jeanne_walk": ("jeanne", "walk_a walk_b", 180, True),
    "jeanne_attack": ("jeanne", "windup slash followthrough", 125, False),
    "jeanne_hit": ("jeanne", "hit", 240, False),
    "jeanne_ko": ("jeanne", "ko", 500, False),
    "wolf_walk": ("wolf", "walk_a walk_b", 180, True),
    "wolf_pounce": ("wolf", "crouch pounce leap", 135, False),
    "wolf_ko": ("wolf", "ko", 500, False),
    "spearman_walk": ("spearman", "walk_a walk_b", 190, True),
    "spearman_attack": ("spearman", "windup thrust recover", 145, False),
    "spearman_guard": ("spearman", "guard block", 240, False),
    "spearman_ko": ("spearman", "ko", 500, False),
    "vfx_moon": ("vfx", "moon_small moon_large moon_break moon_dissolve", 95, False),
    "vfx_spark": ("vfx", "spark_small spark_burst spark_fragments spark_dissolve", 85, False),
    "vfx_dust": ("vfx", "dust_small dust_large dust_wide dust_dissolve", 110, False),
    "vfx_arc": ("vfx", "arc_start arc_grow arc_complete arc_dissolve", 95, False),
}


def matte_image(image, *, effects=False):
    """Heuristic detour: original sheets have a largely opaque glow backdrop.

    This is a preproduction mask: inspect hair, props and magical glows manually.
    """
    import cv2
    import numpy as np
    from PIL import Image
    rgba = np.asarray(image.convert("RGBA")).copy()
    gray = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2GRAY)
    texture = cv2.absdiff(gray, cv2.GaussianBlur(gray, (0, 0), 4))
    rough = (texture > (8 if effects else 13)).astype(np.uint8)
    side = 5 if effects else 11
    rough = cv2.morphologyEx(rough, cv2.MORPH_CLOSE,
                             np.ones((side, side), np.uint8))
    side = 3 if effects else 7
    rough = cv2.dilate(rough, np.ones((side, side), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(rough, 8)
    if count < 2:
        return image
    largest = stats[1:, cv2.CC_STAT_AREA].max()
    mask = np.zeros(gray.shape, np.uint8)
    for index in range(1, count):
        threshold = max(12, largest * (0.006 if effects else 0.055))
        if stats[index, cv2.CC_STAT_AREA] > threshold:
            mask[labels == index] = 255
    outlines, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(mask, outlines, -1, 255, -1)
    if not effects:
        mask = cv2.erode(mask, np.ones((5, 5), np.uint8))
    mask = cv2.GaussianBlur(mask, (3, 3), .7)
    rgba[:, :, 3] = np.minimum(rgba[:, :, 3], mask)
    return Image.fromarray(rgba, "RGBA")


def build_registry(sprites):
    entries = [{"id": sprite["id"], "kind": "sprite",
                "path": sprite["path"]} for sprite in sprites]
    for animation_id, (group, poses, millis, loop) in ANIMATIONS.items():
        entries.append({"id": "anim_" + animation_id, "kind": "animation", "loop": loop,
                        "frames": [{"sprite": f"{group}_{pose}", "duration_ms": millis}
                                   for pose in poses.split()]})
    return {"version": 1, "entries": entries, "bindings": {}}


def build(input_dir, output_dir, *, matte=True, force=False):
    from PIL import Image
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    missing = [filename for _, filename, _, _, _ in SHEETS
               if not (input_dir / filename).is_file()]
    if missing:
        raise FileNotFoundError("Missing source sheets: " + ", ".join(missing))
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(f"{output_dir} is not empty; use --force")
    output_dir.mkdir(parents=True, exist_ok=True)
    sprites, sheets = [], []
    for group, filename, cols, rows, names in SHEETS:
        path = input_dir / filename
        with Image.open(path) as source:
            original = source.convert("RGBA")
        width, height = original.size
        poses = names.split()
        if len(poses) != cols * rows:
            raise ValueError(f"{group}: invalid grid")
        for n, name in enumerate(poses):
            row, col = divmod(n, cols)
            rect = (width * col // cols, height * row // rows,
                    width * (col + 1) // cols, height * (row + 1) // rows)
            frame = original.crop(rect)
            if matte:
                frame = matte_image(frame, effects=group == "vfx")
            target = output_dir / "sprites" / group / (name + ".png")
            target.parent.mkdir(parents=True, exist_ok=True)
            frame.save(target, compress_level=3)
            sprites.append({"id": f"{group}_{name}", "kind": "sprite",
                            "path": target.relative_to(output_dir).as_posix(),
                            "sheet": group, "cell": [col, row],
                            "frame_size": list(frame.size),
                            "pivot": [frame.width // 2, int(frame.height * .9)]})
        sheets.append({"id": group, "original_filename": filename,
                       "columns": cols, "rows": rows, "frame_count": len(poses),
                       "sha256": sha256(path.read_bytes()).hexdigest()})
    (output_dir / "index.json").write_text(json.dumps({
        "schema_version": 1, "sheets": sheets, "sprites": sprites,
        "notes": "single-view concept poses; not direction-complete or loop-seamless"
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "registry.json").write_text(json.dumps(
        build_registry(sprites), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return len(sprites)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("assets/watercolor"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-matte", action="store_true")
    args = parser.parse_args(argv)
    print(f"Exported {build(args.input_dir, args.output_dir, force=args.force, matte=not args.no_matte)} sprites")


if __name__ == "__main__":
    main()
