"""R7.C Jeanne visual art kit: deterministic authored outfit overlays and runtime pack.

The legacy approved Jeanne source is never modified. This opt-in build writes
editable directional garment layers, a Character v1 recipe and the canonical
AssetRegistry v1 pack for R3/R5/R12. Pillow is authoring-only.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

from .characters import (
    DIRECTIONS, CharacterError, atlas_variant, diagnostics, export_pack,
    validate,
)

OUTFITS = ("peasant", "apprentice", "armor", "wounded")
ROW_LAYOUT = {"idle": (0, 1), "walk": (2, 3),
              "attack": (4, 5), "hit": (6,), "death": (7,)}
PORTRAITS = ("neutral", "smile", "determined")
CANVAS = (64, 64)
UPSCALE = 4

# Purposeful silhouette/texture changes rather than false renamed atlas rows.
PALETTES = {
    "peasant": {
        "base": "#efe0bd", "shadow": "#bba17f", "trim": "#744b37",
        "accent": "#6c86a2", "highlight": "#fff1d4",
    },
    "apprentice": {
        "base": "#576c86", "shadow": "#344357", "trim": "#b8915e",
        "accent": "#9d744d", "highlight": "#aec4d5",
    },
    "armor": {
        "base": "#9cabbc", "shadow": "#4d627a", "trim": "#e9c479",
        "accent": "#33486d", "highlight": "#e4f3fa",
    },
    "wounded": {
        "base": "#b59d94", "shadow": "#624b48", "trim": "#9a4145",
        "accent": "#d6ccbb", "highlight": "#efe5d9",
    },
}


def render_garment(outfit, direction):
    """Rasterize a hand-authored 64x64 garment as a modular directional layer.

    Geometry is authored in normalized atlas coordinates, not stretched copies
    of one flat recolor. South = collar/apron front; north = back/cape.
    East/west have distinct side silhouettes, mirrored around the same pivot.
    """
    from PIL import Image, ImageDraw
    if outfit not in OUTFITS or direction not in DIRECTIONS:
        raise CharacterError("Unknown costume or direction")
    scale = UPSCALE
    image = Image.new("RGBA", (CANVAS[0] * scale, CANVAS[1] * scale))
    brush = ImageDraw.Draw(image, "RGBA")
    palette = PALETTES[outfit]
    def rgba(hexcode, alpha=255):
        return tuple(bytes.fromhex(hexcode[1:])) + (alpha,)
    def poly(points, color, alpha=245):
        brush.polygon([(round(x * scale), round(y * scale)) for x, y in points],
                      fill=rgba(palette[color] if color in palette else color, alpha))
    def line(points, color, thickness=1, alpha=245):
        brush.line([(round(x * scale), round(y * scale)) for x, y in points],
                   fill=rgba(palette[color] if color in palette else color, alpha),
                   width=max(1, thickness * scale), joint="curve")
    def ellipse(box, color, alpha=255):
        brush.ellipse(tuple(round(value * scale) for value in box),
                      fill=rgba(palette[color] if color in palette else color, alpha))
    side = direction in ("east", "west")
    back = direction == "north"
    if side:
        # Side silhouette is asymmetrical, then flipped to face the other side.
        poly([(19, 24), (37, 23), (45, 32), (44, 48), (38, 54),
              (20, 52), (15, 42)], "shadow")
        poly([(19, 27), (37, 25), (42, 34), (41, 48),
              (32, 53), (18, 49)], "base")
        if outfit == "peasant":
            poly([(28, 38), (45, 43), (49, 56), (24, 55)], "accent")
            line([(29, 38), (42, 42), (46, 53)], "trim")
            line([(20, 31), (38, 33)], "highlight")
        elif outfit == "apprentice":
            poly([(30, 37), (47, 43), (49, 55), (26, 53)], "accent")
            line([(19, 34), (41, 39)], "trim", 2)
            ellipse((34, 36, 37, 39), "highlight")
        elif outfit == "armor":
            poly([(16, 25), (30, 21), (35, 30), (31, 37), (17, 37)], "shadow")
            poly([(20, 27), (33, 23), (38, 30), (34, 35)], "highlight")
            line([(23, 33), (38, 38), (41, 46)], "trim", 2)
            poly([(30, 36), (44, 35), (47, 45), (39, 50)], "shadow")
            line([(31, 37), (41, 39)], "highlight")
        else:
            poly([(20, 36), (43, 40), (47, 52), (28, 51)], "accent")
            line([(21, 28), (37, 32), (40, 37)], "highlight", 3)
            line([(35, 39), (43, 45)], "trim", 2)
        if direction == "west":
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    else:
        # Different front/back garment anatomy; feet remain unobscured.
        poly([(19, 24), (44, 24), (48, 35), (47, 52),
              (40, 57), (22, 57), (16, 47), (17, 32)], "shadow")
        poly([(20, 25), (43, 25), (45, 34), (44, 50),
              (39, 56), (23, 56), (19, 46), (19, 33)], "base")
        if back:
            poly([(20, 28), (43, 28), (48, 40), (50, 56),
                  (37, 59), (23, 58), (15, 55), (17, 39)], "accent")
            line([(21, 29), (30, 35), (41, 29)], "trim", 2)
            line([(17, 49), (29, 54), (45, 50)], "shadow", 2)
            if outfit == "armor":
                poly([(25, 29), (41, 29), (39, 37), (25, 39)], "shadow")
                line([(27, 30), (36, 33)], "highlight")
            if outfit == "wounded":
                line([(20, 43), (44, 48)], "highlight", 3)
                line([(23, 52), (39, 53)], "trim", 2)
        elif outfit == "peasant":
            # Cream blouse, leather corset and flared blue-gray skirt.
            poly([(23, 31), (41, 31), (44, 41), (39, 46),
                  (24, 46), (20, 40)], "trim")
            poly([(25, 35), (39, 35), (39, 44), (25, 44)], "base")
            poly([(24, 44), (40, 44), (47, 54), (43, 58),
                  (19, 58), (17, 53)], "accent")
            poly([(27, 45), (36, 45), (39, 56), (23, 56)], "highlight", 215)
            line([(31, 32), (31, 43)], "shadow")
            for y in (35, 39, 43):
                line([(27, y), (35, y + 1)], "trim")
        elif outfit == "apprentice":
            poly([(21, 30), (43, 29), (47, 44), (43, 55),
                  (19, 55), (16, 44)], "accent")
            line([(20, 30), (44, 35)], "trim", 3)
            line([(38, 31), (21, 47)], "highlight", 2)
            poly([(25, 45), (40, 45), (42, 56), (21, 56)], "base")
            ellipse((29, 34, 35, 40), "trim")
        elif outfit == "armor":
            poly([(17, 25), (27, 21), (31, 31), (22, 38), (15, 34)], "shadow")
            poly([(35, 21), (46, 25), (49, 34), (40, 38), (33, 30)], "shadow")
            poly([(23, 26), (39, 26), (44, 35), (39, 47),
                  (25, 47), (20, 35)], "highlight")
            poly([(25, 29), (39, 29), (41, 36), (35, 44),
                  (27, 44), (23, 36)], "base")
            line([(31, 29), (31, 44)], "shadow")
            line([(24, 35), (39, 35)], "trim")
            poly([(21, 45), (41, 45), (45, 54), (22, 55)], "accent")
            line([(21, 46), (43, 46)], "trim", 2)
            for x in (24, 40):
                ellipse((x, 47, x + 2, 49), "highlight")
        else:  # wounded: torn outer tunic, bandages, distinct silhouette.
            poly([(20, 37), (43, 39), (47, 49), (42, 53),
                  (47, 57), (37, 58), (26, 54), (18, 58),
                  (16, 45)], "accent")
            poly([(22, 30), (43, 32), (40, 43), (24, 44)], "shadow")
            line([(18, 29), (45, 36)], "highlight", 4)
            line([(19, 34), (42, 41)], "accent", 3)
            line([(26, 48), (40, 53)], "trim", 2)
    # The upper-body neckline/shoulder outline is deliberately light,
    # preserving the approved hair/face, ground shadow and foot pivot.
    if outfit in ("peasant", "apprentice"):
        line([(23, 26), (31, 31), (41, 26)], "highlight")
    if outfit == "wounded":
        line([(17, 31), (25, 34)], "highlight", 3)
    return image.resize(CANVAS, Image.Resampling.LANCZOS)


def _copy_new(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    data = Path(source).read_bytes()
    if target.exists():
        if target.read_bytes() != data:
            raise CharacterError("Refusing to replace existing artwork: " + str(target))
        return
    target.write_bytes(data)


def _new_png(image, target):
    from io import BytesIO
    stream = BytesIO()
    image.save(stream, "PNG", optimize=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = stream.getvalue()
    if target.exists():
        if target.read_bytes() != data:
            raise CharacterError("Refusing to replace existing garment: " + str(target))
        return
    target.write_bytes(data)


def generate_recipe(destination):
    """Describe fully editable four-direction costumes using the R7 v1 schema."""
    base = "sources/jeanne_atlas.png"
    variants = {}
    for variant in OUTFITS:
        block = atlas_variant(
            {"peasant": "Jeanne paysanne — Valcroix",
             "apprentice": "Jeanne apprentie — entraînement",
             "armor": "Jeanne en armure — chevalerie",
             "wounded": "Jeanne blessée — campagne"}[variant],
            base, rows=ROW_LAYOUT,
        )
        block["layers"] = [{
            "slot": "clothing",
            "paths": {direction: f"layers/{variant}/{direction}.png"
                      for direction in DIRECTIONS},
            "offset": [0, 0], "tint": "#ffffff", "opacity": 255,
        }]
        block["expressions"] = {
            key: f"sources/jeanne_{key}.png" for key in PORTRAITS
        }
        variants[variant] = block
    return validate({
        "version": 1, "id": "jeanne", "name": "Jeanne d'Arc",
        "size": [64, 64], "pivot": [32, 63], "variants": variants,
    })


def build_jeanne_art(repository, destination):
    """Build a standalone portable AUTHORING directory and its runtime atlas."""
    repository = Path(repository).resolve()
    destination = Path(destination).resolve()
    if destination == repository or repository.is_relative_to(destination):
        raise CharacterError("Cannot overwrite the source repository")
    art = repository / "sporebound/content/art/jeanne"
    source = art / "jeanne_atlas.png"
    from PIL import Image
    with Image.open(source) as base:
        if base.size != (256, 512):
            raise CharacterError("Unexpected approved Jeanne atlas dimensions")
    _copy_new(source, destination / "sources/jeanne_atlas.png")
    for portrait in PORTRAITS:
        _copy_new(art / f"jeanne_{portrait}.png",
                  destination / "sources" / f"jeanne_{portrait}.png")
    for outfit in OUTFITS:
        for direction in DIRECTIONS:
            _new_png(render_garment(outfit, direction),
                     destination / f"layers/{outfit}/{direction}.png")
    recipe = generate_recipe(destination)
    problems = [issue for issue in diagnostics(recipe, require_outfits=True)
                if issue["severity"] == "error"]
    if problems:
        raise CharacterError("R7 strict QA: " + json.dumps(problems))
    recipe_path = destination / "jeanne.character.json"
    encoded = (json.dumps(recipe, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if recipe_path.exists() and recipe_path.read_bytes() != encoded:
        raise CharacterError("Refusing to replace an edited character recipe")
    if not recipe_path.exists():
        recipe_path.write_bytes(encoded)
    export_pack(recipe, destination, destination / "runtime", strict=True)
    return recipe


def main(argv=None):
    parser = argparse.ArgumentParser(description="Author four Jeanne costume variants")
    parser.add_argument("--repository", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True,
                        help="Existing or new dedicated authoring directory")
    args = parser.parse_args(argv)
    recipe = build_jeanne_art(args.repository, args.output)
    print("Jeanne R7:", ", ".join(recipe["variants"]),
          "| authoring:", args.output / "jeanne.character.json",
          "| Player:", args.output / "runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
