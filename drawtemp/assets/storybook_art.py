"""Original coherent chibi parts, authored procedurally as transparent RGBA.

These are editable SOURCE drawings, not AI-sliced sprites or mirrored fake
animation frames. Outputs are real 192x192 four-facing PNGs with one shared
coordinate system. No gameplay logic or external asset downloads.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SIZE = 192
SCALE = 3
DIRECTIONS = ("front", "right", "back", "left")
COLLECTION = "storybook_v1"
# Names are intentionally namespaced: never replace a historical hero PNG.
FAMILIES = {
    "body": ("slender", "sturdy", "child"),
    "head_shape": ("oval", "soft", "young"),
    "front_hair": ("swept", "fringe", "spikes", "curtain", "waves", "braid_bangs"),
    "rear_hair": ("crop", "long", "ponytail", "braids", "curls", "bob"),
    "top": ("tunic", "brigandine", "mage_robe", "hoodie"),
    "bottom": ("travel_pants", "shorts", "skirt", "leather_boots"),
    "face": ("calm", "smile", "focused"),
    "eyes": ("bright", "narrow", "gentle"),
}
INK = "#403446"
SKIN = "#f1c79e"
SKIN_SHADOW = "#c89178"
HAIR = "#e3b76c"
HAIR_SHADOW = "#976844"
HAIR_LIGHT = "#fff0aa"
CLOTH = "#6489a6"
CLOTH_DARK = "#385c7c"
LINING = "#f2dcaa"


class Brush:
    """Subpixel line art: draw at 3x then downsample for smooth in-game art."""
    def __init__(self):
        from PIL import Image, ImageDraw
        self.image = Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE))
        self.d = ImageDraw.Draw(self.image, "RGBA")

    def _pt(self, seq):
        return [round(v * SCALE) for v in seq]

    def ellipse(self, box, fill, outline=INK, width=2):
        self.d.ellipse(self._pt(box), fill=fill, outline=outline,
                       width=max(1, round(width * SCALE)) if outline else 1)

    def poly(self, coords, fill, outline=INK, width=2):
        points = [(round(x * SCALE), round(y * SCALE)) for x, y in coords]
        self.d.polygon(points, fill=fill)
        if outline:
            self.d.line(points + points[:1], fill=outline,
                        width=round(width * SCALE), joint="curve")

    def line(self, coords, fill, width=2):
        pts = [(round(x * SCALE), round(y * SCALE)) for x, y in coords]
        self.d.line(pts, fill=fill, width=max(1, round(width * SCALE)),
                    joint="curve")

    def rounded(self, box, radius, fill, outline=INK, width=2):
        self.d.rounded_rectangle(self._pt(box), round(radius * SCALE),
                                 fill=fill, outline=outline,
                                 width=max(1, round(width * SCALE)))

    def finish(self, direction):
        from PIL import Image, ImageOps
        result = self.image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
        if direction == "left":
            result = ImageOps.mirror(result)
        return result


def _hair(p, kind, name, d):
    """Hair shares scalp anchors, creating interchangeable aligned layers."""
    back = d == "back"
    side = d in ("left", "right")
    if kind == "rear_hair":
        length = {"crop": 98, "long": 146, "ponytail": 133,
                  "braids": 138, "curls": 128, "bob": 118}[name]
        p.ellipse((61, 52, 132, length), HAIR_SHADOW, INK, 2.5)
        p.ellipse((67, 50, 126, min(112, length)), HAIR, None)
        if name == "ponytail":
            p.ellipse((118, 64, 145, 94), HAIR, INK)
            p.poly([(132, 78), (151, 107), (142, 139), (126, 129),
                    (133, 105)], HAIR_SHADOW)
            p.ellipse((126, 84, 143, 101), CLOTH_DARK, INK, 1)
        if name == "braids":
            for x in (67, 125):
                p.line([(x, 95), (x - 2, 116), (x + 2, 136)], HAIR_SHADOW, 12)
                for y in range(99, 134, 9):
                    p.ellipse((x-6, y-5, x+6, y+6), HAIR, INK, 1.5)
        if name == "curls":
            for x, y in ((68, 90), (122, 93), (61, 112), (130, 112),
                         (74, 126), (118, 127)):
                p.ellipse((x-10, y-8, x+10, y+11), HAIR, INK, 1.4)
        if name == "long":
            for x in (72, 83, 112, 123):
                p.line([(x, 98), (x-3, 121), (x, 143)],
                       HAIR_LIGHT if x % 2 else HAIR_SHADOW, 2)
        if name == "bob":
            p.line([(67, 100), (74, 115), (94, 117), (115, 114),
                    (126, 98)], HAIR_LIGHT, 2.2)
        if name == "crop":
            p.line([(75, 89), (94, 94), (117, 89)],
                   HAIR_LIGHT, 3)
        return

    # Front Hair is a true separate silhouette, NOT a crop of Rear Hair.
    p.ellipse((63, 49, 132, 91), HAIR_SHADOW, INK, 2.4)
    p.ellipse((69, 49, 125, 85), HAIR, None)
    if name == "swept":
        p.poly([(66, 68), (77, 55), (120, 56), (130, 72),
                (113, 77), (94, 83), (70, 89)], HAIR)
        p.poly([(70, 78), (97, 63), (115, 62),
                (95, 91), (74, 94)], HAIR_LIGHT, None)
    elif name == "fringe":
        for x, y in ((66, 96), (80, 105), (95, 97), (109, 102),
                     (124, 93)):
            p.poly([(x-11, 67), (x+9, 66), (x+3, y)], HAIR, INK, 1.4)
    elif name == "spikes":
        for x, y in ((59, 53), (73, 39), (88, 43), (104, 37),
                     (120, 43), (134, 62)):
            p.poly([(x-9, 73), (x, y), (x+11, 73)], HAIR, INK, 1.8)
        p.poly([(71, 75), (89, 85), (100, 73), (119, 86),
                (125, 75)], HAIR, INK, 1.4)
    elif name == "curtain":
        p.poly([(67, 65), (92, 57), (96, 65), (91, 95),
                (72, 108), (63, 94)], HAIR)
        p.poly([(98, 62), (116, 58), (131, 71), (128, 101),
                (111, 107), (99, 91)], HAIR)
    elif name == "waves":
        for x in (70, 85, 104, 120):
            p.ellipse((x-14, 61, x+11, 93), HAIR, INK, 1.8)
            p.line([(x-8, 73), (x, 66), (x+8, 75)],
                   HAIR_LIGHT, 2.2)
    elif name == "braid_bangs":
        p.poly([(65, 67), (75, 59), (123, 61), (129, 86),
                (110, 88), (96, 78), (74, 89)], HAIR)
        for x in range(74, 117, 10):
            p.ellipse((x-4, 64, x+7, 77), HAIR_LIGHT, INK, 1.2)
    p.line([(74, 58), (94, 53), (115, 59)], HAIR_LIGHT, 2.5)
    if side:
        p.poly([(124, 67), (134, 87), (122, 105), (115, 85)],
               HAIR_SHADOW, INK, 1.4)


def _head(p, name, d):
    side = d in ("left", "right")
    sizes = {
        "oval": (64, 57, 128, 127),
        "soft": (62, 58, 130, 129),
        "young": (66, 66, 126, 128),
    }
    x1, y1, x2, y2 = sizes[name]
    if side:
        x1 += 3
        x2 += 3
    p.ellipse((x1, y1, x2, y2), SKIN_SHADOW, INK, 2.6)
    p.ellipse((x1+4, y1+3, x2-5, y2-7), SKIN, None)
    if d != "back":
        if side:
            p.ellipse((x2-6, 93, x2+9, 108), SKIN, INK, 1.6)
            p.poly([(x2-3, 107), (x2+4, 111), (x2-2, 116)],
                   SKIN_SHADOW, None)
        else:
            for x in (x1+1, x2-9):
                p.ellipse((x, 97, x+11, 111), SKIN, INK, 1.3)
    else:
        p.line([(78, 70), (97, 64), (116, 71)], "#ffd9b3", 2.2)
    p.ellipse((x1+10, y1+8, x1+27, y1+18),
              (255, 244, 220, 110), None)


def _body(p, name, d):
    # Original adult/child bodies with distinct shoulder, arm and leg poses.
    spec = {
        "slender": (70, 123, 122, 172, 12),
        "sturdy": (65, 120, 127, 173, 17),
        "child": (77, 126, 115, 169, 11),
    }
    l, top, r, bottom, arm = spec[name]
    center = (l+r)/2
    # Rearward arms for left/right, reversed naturally for left.
    for x in (l-arm, r-3):
        p.rounded((x, top+8, x+arm+3, bottom-5), 6,
                  SKIN_SHADOW, INK, 2)
        p.ellipse((x+2, bottom-9, x+arm+1, bottom+2),
                  SKIN, INK, 1.7)
    p.rounded((l, top, r, bottom), 12, SKIN, INK, 2.6)
    leg_offset = 6 if name == "child" else 0
    for x in (l+8, center+5):
        p.rounded((x, bottom-5, x+15, 187-leg_offset), 5,
                  SKIN_SHADOW, INK, 2)
        p.ellipse((x-1, 181-leg_offset, x+17, 190-leg_offset),
                  "#755d54", INK, 1.5)
    p.line([(center, bottom-12), (center, bottom+7-leg_offset)],
           "#6d5a5b", 2)
    if d == "back":
        p.line([(l+10, top+10), (r-10, top+12)], "#ffe6bf", 2)


def _top(p, name, d):
    colors = {
        "tunic": ("#749f9f", "#3d777e"),
        "brigandine": ("#77839f", "#45536d"),
        "mage_robe": ("#937bb8", "#5a4a82"),
        "hoodie": ("#d38f76", "#9c5a56"),
    }
    fill, shadow = colors[name]
    body = [(69, 119), (83, 112), (107, 112), (124, 120),
            (126, 157), (117, 165), (76, 165), (66, 155)]
    p.poly(body, shadow, INK, 2.4)
    p.poly([(72, 123), (83, 117), (107, 117), (120, 125),
            (118, 156), (77, 156)], fill, None)
    p.poly([(66, 124), (72, 120), (83, 127), (78, 146),
            (66, 145)], fill)
    p.poly([(111, 126), (122, 121), (130, 127), (128, 145),
            (115, 147)], fill)
    if name == "brigandine":
        p.poly([(78, 119), (95, 132), (110, 119), (116, 144),
                (96, 151), (76, 143)], "#bdc3c6", INK, 1.6)
        p.line([(78, 133), (115, 133)], "#53627a", 2)
        for x in (82, 111):
            p.ellipse((x-3, 134, x+3, 140), "#f5d486", INK, 1)
    elif name == "mage_robe":
        p.poly([(75, 148), (119, 148), (131, 177),
                (63, 177)], fill, INK, 2)
        p.line([(96, 118), (96, 166)], LINING, 3)
        p.ellipse((91, 137, 102, 148), "#e8ce78", INK, 1.2)
    elif name == "hoodie":
        p.ellipse((73, 107, 117, 134), shadow, INK, 2)
        p.poly([(80, 118), (96, 130), (111, 118)],
               "#e6c59d", None)
        p.rounded((83, 140, 109, 152), 4, shadow, None)
    else:
        p.poly([(84, 116), (96, 127), (110, 117)], LINING, INK, 1.3)
        p.line([(74, 148), (117, 148)], "#b48a56", 5)
        p.ellipse((92, 143, 101, 152), "#edd18b", INK, 1)
    p.line([(78, 127), (77, 143)], (255, 255, 255, 95), 2)
    if d == "back":
        p.poly([(87, 112), (106, 112), (118, 125),
                (95, 137), (76, 126)], shadow, None)


def _bottom(p, name, d):
    if name == "skirt":
        p.poly([(77, 156), (115, 156), (131, 179),
                (64, 179)], "#a68bb1", INK, 2.4)
        p.line([(69, 174), (125, 174)], "#d5b9d5", 2)
        for x in (77, 91, 107, 119):
            p.line([(x, 165), (x-4, 176)], "#664f88", 1.2)
    else:
        cut = 174 if name == "shorts" else 185
        color = "#6a758b" if name != "leather_boots" else "#8f6850"
        for x in (75, 99):
            p.rounded((x, 157, x+18, cut), 5, color, INK, 2)
            p.line([(x+5, 164), (x+5, cut-3)], "#b2b6c2", 2)
        if name == "leather_boots":
            for x in (74, 100):
                p.rounded((x, 174, x+20, 188), 4,
                          "#79563c", INK, 2)
                p.line([(x+4, 181), (x+16, 181)], "#dcc28c", 2)
    p.line([(78, 159), (116, 159)], LINING, 2)
    if d == "back":
        p.line([(85, 164), (108, 164)], "#d6c6aa", 2)


def _face(p, name, d):
    if d == "back":
        return
    if d in ("right", "left"):
        p.line([(112, 106), (119, 109), (114, 113)], SKIN_SHADOW, 2)
        if name == "smile":
            p.line([(109, 116), (116, 118)], "#7d4853", 2)
        return
    p.ellipse((73, 104, 85, 112), (223, 126, 122, 94), None)
    p.ellipse((108, 104, 120, 112), (223, 126, 122, 94), None)
    if name == "smile":
        p.line([(89, 114), (97, 119), (104, 114)], "#885762", 2.2)
    elif name == "focused":
        p.line([(90, 116), (103, 115)], "#734958", 2)
        p.line([(79, 87), (90, 89)], "#6a4c4d", 2)
        p.line([(104, 89), (116, 87)], "#6a4c4d", 2)
    else:
        p.line([(91, 115), (102, 115)], "#8a6067", 2)


def _eyes(p, name, d):
    if d == "back":
        return
    if d in ("right", "left"):
        p.ellipse((107, 88, 118, 101), "#f9f5ef", INK, 1.4)
        p.ellipse((112, 91, 117, 99), "#537690", None)
        return
    specs = {
        "bright": ((78, 88, 91, 102), (102, 88, 115, 102)),
        "narrow": ((78, 92, 91, 101), (102, 92, 115, 101)),
        "gentle": ((79, 90, 91, 101), (102, 90, 114, 101)),
    }
    for x1, y1, x2, y2 in specs[name]:
        p.ellipse((x1, y1, x2, y2), "#fff9ef", INK, 1.7)
        p.ellipse((x1+5, y1+2, x2-2, y2-1),
                  "#567c96", INK, 0.8)
        p.ellipse((x1+6, y1+3, x1+9, y1+6),
                  "#ffffff", None)
        if name == "narrow":
            p.line([(x1-1, y1+2), (x2+1, y1)], INK, 2.3)


DRAWERS = {
    "body": _body, "head_shape": _head, "front_hair": _hair,
    "rear_hair": _hair, "top": _top, "bottom": _bottom,
    "face": _face, "eyes": _eyes,
}


def render_piece(slot, style, facing):
    """Paint unique four-direction PNG art; never invent action animation."""
    if slot not in FAMILIES or style not in FAMILIES[slot]:
        raise ValueError(f"Unknown original part {slot}/{style}")
    if facing not in DIRECTIONS:
        raise ValueError(f"Unknown direction {facing}")
    direction = "right" if facing == "left" else facing
    painter = Brush()
    if slot in ("front_hair", "rear_hair"):
        _hair(painter, slot, style, direction)
    else:
        DRAWERS[slot](painter, style, direction)
    return painter.finish(facing)


def build(root, *, overwrite=False):
    """Materialize a deterministic complete pack of game-ready 192x192 PNG.

    Existing names are never touched because all assets are namespaced.
    Files are written atomically to avoid partially generated family sets.
    """
    root = Path(root).resolve()
    dest = root / "assets" / "hero_parts"
    dest.mkdir(parents=True, exist_ok=True)
    wrote = 0
    for slot, styles in FAMILIES.items():
        folder = dest / slot
        folder.mkdir(parents=True, exist_ok=True)
        for style in styles:
            for facing in DIRECTIONS:
                name = f"{COLLECTION}_{style}_{facing}.png"
                path = folder / name
                if path.exists() and not overwrite:
                    continue
                image = render_piece(slot, style, facing)
                temporary = path.with_suffix(".png.tmp")
                image.save(temporary, format="PNG", optimize=True)
                temporary.replace(path)
                wrote += 1
    return wrote



# Independently drawn compatible layers: 3 silhouettes and 12 different
# outfits/looks; all use the same real directional source family.
STORYBOOK_STARTERS = {
    "male": {
        "body": "slender", "head_shape": "oval",
        "rear_hair": "crop", "front_hair": "swept",
        "face": "calm", "eyes": "bright",
        "top": "tunic", "bottom": "travel_pants",
    },
    "female": {
        "body": "slender", "head_shape": "soft",
        "rear_hair": "long", "front_hair": "waves",
        "face": "smile", "eyes": "gentle",
        "top": "mage_robe", "bottom": "skirt",
    },
    "kid": {
        "body": "child", "head_shape": "young",
        "rear_hair": "bob", "front_hair": "fringe",
        "face": "smile", "eyes": "bright",
        "top": "hoodie", "bottom": "shorts",
    },
}
LOOKS = (
    ("village_scout", "Village Scout", "male",
     {"front_hair": "swept", "rear_hair": "crop", "top": "tunic"}),
    ("iron_guard", "Iron Guard", "male",
     {"body": "sturdy", "front_hair": "spikes",
      "rear_hair": "crop", "top": "brigandine",
      "bottom": "leather_boots", "face": "focused", "eyes": "narrow"}),
    ("wandering_mage", "Wandering Mage", "male",
     {"front_hair": "curtain", "rear_hair": "long",
      "top": "mage_robe", "face": "calm"}),
    ("road_traveller", "Road Traveller", "male",
     {"front_hair": "waves", "rear_hair": "bob",
      "top": "hoodie", "bottom": "travel_pants"}),
    ("forest_archer", "Forest Archer", "female",
     {"front_hair": "braid_bangs", "rear_hair": "ponytail",
      "top": "tunic", "bottom": "travel_pants", "face": "focused"}),
    ("village_healer", "Village Healer", "female",
     {"front_hair": "fringe", "rear_hair": "braids",
      "top": "mage_robe", "bottom": "skirt"}),
    ("castle_knight", "Castle Knight", "female",
     {"front_hair": "swept", "rear_hair": "bob",
      "top": "brigandine", "bottom": "leather_boots"}),
    ("wandering_scholar", "Wandering Scholar", "female",
     {"front_hair": "curtain", "rear_hair": "curls",
      "top": "tunic", "bottom": "skirt"}),
    ("village_kid", "Village Kid", "kid",
     {"front_hair": "fringe", "rear_hair": "bob", "top": "hoodie"}),
    ("young_scout", "Young Scout", "kid",
     {"front_hair": "spikes", "rear_hair": "crop", "top": "tunic"}),
    ("apprentice_mage", "Apprentice Mage", "kid",
     {"front_hair": "waves", "rear_hair": "curls",
      "top": "mage_robe"}),
    ("young_guard", "Young Guard", "kid",
     {"front_hair": "swept", "rear_hair": "crop",
      "top": "brigandine", "face": "focused"}),
)


def _layer(slot, style):
    from .character_parts import PART_CATEGORIES
    from .characters import DIRECTIONS
    suffixes = {
        "south": "front", "north": "back",
        "east": "right", "west": "left",
    }
    name = f"{COLLECTION}_{style}"
    return {
        "slot": slot,
        "paths": {direction:
            f"assets/hero_parts/{slot}/{name}_{suffixes[direction]}.png"
            for direction in DIRECTIONS},
        "offset": [0, 0], "tint": "#ffffff", "opacity": 255,
    }


def _variant(pieces, label):
    from .characters import frame, DIRECTIONS
    from .character_parts import PART_CATEGORIES
    base = "assets/hero_parts/accessory/none_"
    suffixes = {
        "south": "front", "north": "back",
        "east": "right", "west": "left",
    }
    return {
        "name": label, "expressions": {},
        "clips": {"idle": {"loop": True, "directions": {
            direction: [frame(base + suffixes[direction] + ".png")]
            for direction in DIRECTIONS}}},
        "layers": [_layer(slot, pieces[slot]) for slot, _ in PART_CATEGORIES
                   if slot in pieces],
    }


def storybook_starter():
    """R7 recipe using ONLY coherent storybook v1 parts and real idle art."""
    from .characters import validate
    return validate({
        "version": 1, "id": "storybook_hero",
        "name": "Storybook Hero · Original Art",
        "size": [SIZE, SIZE], "pivot": [SIZE//2, SIZE-1],
        "variants": {
            profile: _variant(pieces, profile.capitalize())
            for profile, pieces in STORYBOOK_STARTERS.items()},
    })


def available_storybook_looks(profile=None):
    if profile is not None and profile not in STORYBOOK_STARTERS:
        raise ValueError("Unknown storybook profile")
    return tuple({"id": key, "name": name, "profile": kind}
                 for key, name, kind, _ in LOOKS
                 if profile in (None, kind))


def apply_storybook_look(document, variant, look_id):
    """Apply coherent original layer set, preserving all authored clips."""
    from .character_parts import PART_CATEGORIES
    from .characters import validate
    validate(document)
    if document["size"] != [SIZE, SIZE] or variant not in document["variants"]:
        raise ValueError("Storyboard look requires a 192x192 character variant")
    match = next((entry for entry in LOOKS if entry[0] == look_id), None)
    if match is None:
        raise ValueError("Unknown storybook look")
    profile = match[2]
    pieces = dict(STORYBOOK_STARTERS[profile])
    pieces.update(match[3])
    target = document["variants"][variant]["layers"]
    allowed = set(FAMILIES)
    target[:] = [layer for layer in target if layer["slot"] not in allowed]
    target.extend(_layer(slot, pieces[slot])
                  for slot, _ in PART_CATEGORIES if slot in pieces)
    validate(document)



def contact_sheet(root, output):
    """Visual QA board of twelve real exported looks, all four facings."""
    from PIL import Image, ImageDraw
    from .characters import render_frame
    from copy import deepcopy

    root = Path(root).resolve()
    build(root)
    original = storybook_starter()
    board = Image.new("RGB", (4 * 224 + 32, 12 * 220 + 48), "#eaf0f6")
    d = ImageDraw.Draw(board)
    for index, entry in enumerate(LOOKS):
        key, label, profile, _ = entry
        doc = deepcopy(original)
        apply_storybook_look(doc, profile, key)
        row = index
        d.text((16, row * 220 + 5), f"{profile.title()} · {label}",
               fill="#253249")
        for col, direction in enumerate(("south", "east", "north", "west")):
            sample = render_frame(doc, profile, "idle", direction, 0, root)
            x = 16 + col * 224
            y = 24 + row * 220
            # Transparent checkerboard (only in QA board).
            for cy in range(0, 192, 12):
                for cx in range(0, 192, 12):
                    shade = "#f4f5f8" if (cx // 12 + cy // 12) % 2 else "#dde3ea"
                    d.rectangle((x+cx, y+cy, x+cx+11, y+cy+11),
                                fill=shade)
            board.paste(sample, (x, y), sample)
            d.text((x+4, y+195), direction.upper(), fill="#4a556b")
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    board.save(path, format="PNG", optimize=True)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build original DrawTemp art")
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--force", action="store_true",
                        help="Regenerate only namespaced storybook assets")
    parser.add_argument("--preview", type=Path,
                        help="Save a QA contact sheet of 12 looks x 4 directions")
    args = parser.parse_args(argv)
    changed = build(args.root, overwrite=args.force)
    if args.preview:
        board = contact_sheet(args.root, args.preview)
        print("QA artwork board: " + str(board))
    print(f"{COLLECTION}: {changed} PNG rendered, "
          f"{sum(map(len, FAMILIES.values())) * 4} total, "
          "192x192 RGBA, four facings")


if __name__ == "__main__":
    main()
