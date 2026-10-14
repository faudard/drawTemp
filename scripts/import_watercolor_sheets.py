"""Import the nine user-provided watercolor character, VFX and prop sheets.

Requires optional authoring dependencies (not required by the headless engine)::

    python -m pip install pillow numpy opencv-python-headless
    python scripts/import_watercolor_sheets.py --input-dir /path/to/sheets \
        --output-dir assets/watercolor --force

PNG sheets are NOT direction-complete or seamless animation sprite sheets. The
source is not checked in by this script; provide the originals to regenerate.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

SHEETS = (
    ("vfx", "Planche de 16 effets de combat.png", 4, 4, (
        "moon_small", "moon_large", "moon_break", "moon_dissolve",
        "spark_small", "spark_burst", "spark_fragments", "spark_dissolve",
        "dust_small", "dust_large", "dust_wide", "dust_dissolve",
        "arc_start", "arc_grow", "arc_complete", "arc_dissolve")),
    ("wolf", "Planche d’animation du loup gris.png", 4, 3, (
        "idle", "walk_a", "walk_b", "crouch", "pounce", "leap",
        "growl", "defend", "snarl", "hit", "ko", "howl")),
    ("jeanne", "Jeanne : planche d’action en 12 poses.png", 4, 3, (
        "idle", "walk_a", "walk_b", "ready", "windup", "slash",
        "followthrough", "guard", "hit", "kneel", "ko", "victory")),
    ("spearman", "Planche d’action : douze poses du lancier.png", 4, 3, (
        "idle", "walk_a", "walk_b", "guard", "windup", "thrust",
        "recover", "ready", "block", "hit", "kneel", "ko")),
    ("props", "Douze objets médiévaux modulaires en aquarelle.png", 4, 3, (
        "chapel", "forge", "market_stall", "camp_tent", "stone_bridge",
        "ruined_arch", "oak_tree", "pine_tree", "supply_cart",
        "palisade_gate", "stone_stairs", "treasure_chest")),
    ("townfolk", "Six personnages médiévaux en feuille d’assets.png", 3, 2, (
        "scout", "blacksmith", "messenger", "royal_knight",
        "veteran_commander", "militia_axewoman")),
    ("soldiers", "Six soldats tactiques en aquarelle.png", 3, 2, (
        "bandit", "spearman", "crossbowman", "royal_squire",
        "heavy_guard", "ranger")),
    ("bestiary", "Bestiaire médiéval fantastique en six créatures.png", 3, 2, (
        "wolf", "boar", "bear", "gargoyle", "ogre", "spectral_hound")),
    ("heroes", "Six héros tactiques en aquarelle.png", 3, 2, (
        "jeanne", "knight_captain", "healer", "nun", "red_knight", "english_champion")),
)

# Timing here is preliminary; these are authored poses, not loop-clean footage.
ANIMATIONS = {
    "jeanne_walk": ("jeanne", ("walk_a", "walk_b"), 180, True),
    "jeanne_attack": ("jeanne", ("windup", "slash", "followthrough"), 125, False),
    "jeanne_hit": ("jeanne", ("hit",), 240, False),
    "jeanne_ko": ("jeanne", ("ko",), 500, False),
    "wolf_walk": ("wolf", ("walk_a", "walk_b"), 180, True),
    "wolf_pounce": ("wolf", ("crouch", "pounce", "leap"), 135, False),
    "wolf_ko": ("wolf", ("ko",), 500, False),
    "spearman_walk": ("spearman", ("walk_a", "walk_b"), 190, True),
    "spearman_attack": ("spearman", ("windup", "thrust", "recover"), 145, False),
    "spearman_guard": ("spearman", ("guard", "block"), 240, False),
    "spearman_ko": ("spearman", ("ko",), 500, False),
    "vfx_moon": ("vfx", ("moon_small", "moon_large", "moon_break", "moon_dissolve"), 95, False),
    "vfx_spark": ("vfx", ("spark_small", "spark_burst", "spark_fragments", "spark_dissolve"), 85, False),
    "vfx_dust": ("vfx", ("dust_small", "dust_large", "dust_wide", "dust_dissolve"), 110, False),
    "vfx_arc": ("vfx", ("arc_start", "arc_grow", "arc_complete", "arc_dissolve"), 95, False),
}


def _matte(image, effects=False):
    """Approximate alpha using texture/silhouette; retains original RGB detail.

    The source sheets embed a blurred warm/cool backdrop in near-opaque RGBA,
    therefore merely cropping the source is not sufficient. This is a heuristic
    extraction, with raw source preserved for subsequent hand-cleanup.
    """
    import cv2
    import numpy as np

    rgba = np.asarray(image.convert("RGBA")).copy()
    gray = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (0, 0), 4)
    texture = cv2.absdiff(gray, blur)
    # Source edges have meaningful high-frequency texture; blurred backdrops do not.
    candidate = (texture > (8 if effects else 13)).astype(np.uint8)
    size = 5 if effects else 11
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE,
                                np.ones((size, size), np.uint8))
    candidate = cv2.dilate(candidate, np.ones((3 if effects else 7, ) * 2,
                                              np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(candidate, 8)
    if count <= 1:
        return image
    largest = stats[1:, cv2.CC_STAT_AREA].max()
    mask = np.zeros(gray.shape, np.uint8)
    for i in range(1, count):
        if stats[i, cv2.CC_STAT_AREA] > max(12, largest * (0.006 if effects else 0.055)):
            mask[labels == i] = 255
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(mask, contours, -1, 255, -1)
    if not effects:
        mask = cv2.erode(mask, np.ones((5, 5), np.uint8))
    mask = cv2.GaussianBlur(mask, (3, 3), .7)
    # Keep the source's existing anti-aliasing/translucency in both cases.
    rgba[:, :, 3] = np.minimum(mask, rgba[:, :, 3])
    from PIL import Image
    return Image.fromarray(rgba, "RGBA")


def extract_sheet(sheet, source, target, matte=True):
    """Extract full-grid cells (stable pivots), plus individually trimmed props."""
    from PIL import Image
    group, _filename, cols, rows, names = sheet
    with Image.open(source) as loaded:
        original = loaded.convert('RGBA')
    w, h = original.size
    # Image sheets are 1536x1024; three rows require rounded y boundaries.
    box_dir = target / 'sprites' / group
    box_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for index, name in enumerate(names):
        row, col = divmod(index, cols)
        left, right = (w * col) // cols, (w * (col + 1)) // cols
        top, bottom = (h * row) // rows, (h * (row + 1)) // rows
        image = original.crop((left, top, right, bottom))
        if matte:
            image = _matte(image, effects=group == 'vfx')
        rel = f'sprites/{group}/{name}.png'
        image.save(target / rel, optimize=True)
        records.append({'id': f'{group}_{name}', 'kind': 'sprite',
                        'path': rel, 'sheet': group, 'cell': [col, row],
                        'frame_size': list(image.size),
                        'pivot': [image.width // 2, int(image.height * .9)]})
    return records


def build_registry(records):
    """Emit an AssetRegistry v1-compatible projection without altering gameplay."""
    entries = [{'id': item['id'], 'kind': 'sprite', 'path': item['path']}
               for item in records]
    for aid, (group, frames, duration, loop) in ANIMATIONS.items():
        entries.append({'id': 'anim_' + aid, 'kind': 'animation', 'loop': loop,
                        'frames': [{'sprite': f'{group}_{frame}',
                                    'duration_ms': duration} for frame in frames]})
    return {'version': 1, 'entries': entries, 'bindings': {}}


def build(input_dir, output_dir, *, force=False, matte=True):
    if not input_dir.is_dir():
        raise FileNotFoundError(input_dir)
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(f'{output_dir} not empty; use --force')
    missing = [file for _, file, *_ in SHEETS if not (input_dir / file).is_file()]
    if missing:
        raise FileNotFoundError('Missing source sheets: ' + ', '.join(missing))
    from PIL import Image  # optional dependency only for actual extraction
    output_dir.mkdir(parents=True, exist_ok=True)
    sheets = []
    records = []
    for sheet in SHEETS:
        group, filename, cols, rows, names = sheet
        source = input_dir / filename
        records.extend(extract_sheet(sheet, source, output_dir, matte=matte))
        sheets.append({'id': group, 'original_filename': filename,
                       'columns': cols, 'rows': rows, 'sha256': sha256(source.read_bytes()).hexdigest(),
                       'frame_count': len(names)})
    (output_dir / 'index.json').write_text(json.dumps({
        'schema_version': 1, 'sheets': sheets, 'sprites': records,
        'notes': 'single-view concept poses; not directional/loop seamless',
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output_dir / 'registry.json').write_text(json.dumps(
        build_registry(records), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return len(records)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=Path('assets/watercolor'))
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--no-matte', action='store_true', help='Crop only, retain backgrounds')
    args = parser.parse_args(argv)
    count = build(args.input_dir, args.output_dir,
                  force=args.force, matte=not args.no_matte)
    print(f'Exported {count} watercolor sprites to {args.output_dir}')


if __name__ == '__main__':
    main()
