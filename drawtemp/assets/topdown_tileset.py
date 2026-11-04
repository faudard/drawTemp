"""Original, deterministic 2D starter tileset, PNG-encoded without Pillow.

The embedded starter atlas has 8 materials x 2 graphic variants, 64x64 RGBA
pixels each, laid out in one row. It can be decoded by Qt directly from
memory, including packaged Player builds. No temporary files or permissions.
This is visual-only: authoring/gameplay still use canonical surface tokens.
"""
from __future__ import annotations

from functools import lru_cache
from struct import pack
from zlib import compress, crc32

from drawtemp.render.autotile2d import MATERIALS, TILE_SIZE

VARIANTS = 2
COLORS = {
    "grass": (116, 164, 92),
    "dirt": (173, 129, 84),
    "sand": (220, 190, 126),
    "stone": (144, 153, 158),
    "cobble": (174, 163, 143),
    "rock": (118, 128, 136),
    "water": (64, 131, 185),
    "bridge": (153, 105, 68),
}


def _hash(x, y, salt):
    k = ((x + 29) * 0x45d9f3b ^ (y + 37) * 0x119de1f3 ^
         (salt + 1) * 0x27d4eb2d) & 0xffffffff
    k ^= k >> 16
    k = (k * 0x7feb352d) & 0xffffffff
    k ^= k >> 15
    k = (k * 0x846ca68b) & 0xffffffff
    return (k ^ (k >> 16)) & 0xffffffff


def _pixel(material, x, y, variant):
    """Tiny native-pixel ornaments; no licensed third-party sprites."""
    base = COLORS[material]
    salt = MATERIALS.index(material) * 13 + variant * 97
    value = _hash(x // 2, y // 2, salt)
    grain = (value % 17) - 8
    if material == "grass":
        if (value % 51 == 0) or (y % 13 in (3, 4) and
                                 (x * 13 + salt) % 29 < 3):
            grain -= 28
        if value % 41 == 2:
            grain += 25
    elif material == "water":
        grain = ((x * 5 + y * 11 + salt) % 23) // 3 - 4
        if (y % 13 in (4, 5) and (x + (y // 13) * 9 + salt) % 29 < 15):
            grain += 25
    elif material == "bridge":
        grain = 14 if y % 16 in (0, 1) else grain
        if x % 23 == 0:
            grain -= 14
        if y % 16 == 15:
            grain -= 32
    elif material == "cobble":
        if (y // 12 + x // 17) % 4 == 0:
            grain += 8
        if y % 12 in (0, 1) or (x + (y // 12 % 2) * 9) % 17 in (0, 1):
            grain -= 34
    elif material == "stone":
        if (y % 23 == 0) or ((x + (y // 23 % 2) * 19) % 39 == 0):
            grain -= 23
        elif value % 37 == 0:
            grain += 19
    elif material == "rock":
        grain = (value % 34) - 17
        if (x + y * 3) % 31 < 2:
            grain -= 21
    elif material == "sand":
        grain = (value % 11) - 5
        if value % 31 == 0:
            grain -= 20
    else:  # dirt
        if value % 28 < 3:
            grain -= 22
    return tuple(max(0, min(255, component + grain)) for component in base) + (255,)


def _chunk(tag, payload):
    return pack(">I", len(payload)) + tag + payload + pack(">I", crc32(tag + payload) & 0xffffffff)


@lru_cache(maxsize=1)
def starter_tileset_png():
    """Atlas source (1024x64), with 16 real visual tile sprites."""
    width = len(MATERIALS) * VARIANTS * TILE_SIZE
    height = TILE_SIZE
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # PNG filter: None
        for material in MATERIALS:
            for variant in range(VARIANTS):
                for x in range(TILE_SIZE):
                    rows.extend(_pixel(material, x, y, variant))
    return (b"\x89PNG\r\n\x1a\n" +
            _chunk(b"IHDR", pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) +
            _chunk(b"IDAT", compress(bytes(rows), 9)) +
            _chunk(b"IEND", b""))


@lru_cache(maxsize=len(MATERIALS) * VARIANTS)
def tile_rgba(material, variant=0):
    """Raw 64×64 RGBA art reused by Qt atlas and Tk quarter composition.

    Deterministic, no Pillow, Qt or Tk imports. Cached only for the 16
    original tiles, so neighboring cells never allocate independent art.
    """
    if material not in MATERIALS or type(variant) is not int or variant not in (0, 1):
        raise ValueError("Unknown 2D tileset graphic")
    return bytes(channel
                 for y in range(TILE_SIZE)
                 for x in range(TILE_SIZE)
                 for channel in _pixel(material, x, y, variant))


def atlas_rect(material, variant):
    """Return a validated source crop: 64x64 sprite of selected material."""
    if material not in MATERIALS or type(variant) is not int or variant not in (0, 1):
        raise ValueError("Unknown 2D tileset graphic")
    return ((MATERIALS.index(material) * VARIANTS + variant) * TILE_SIZE,
            0, TILE_SIZE, TILE_SIZE)


__all__ = ["starter_tileset_png", "atlas_rect", "tile_rgba", "COLORS", "VARIANTS"]
