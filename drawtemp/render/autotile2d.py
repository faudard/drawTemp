"""2D quarter-autotile topology shared by the Studio and Player.

The gameplay cell stays whole. These deterministic 2x2 quadrant masks are
rendering-only, computed from existing surfaces/heights and all eight neighbors.
The original Content, movement/collision rules and save format are unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass

from sporebound.terrain_autoblend import LAND_PRIORITY

# Stable single-digit atlas indexes; do not derive from an unordered set.
MATERIALS = ("grass", "dirt", "sand", "stone", "cobble", "rock", "water", "bridge")
OFFSETS = ((0, -1), (1, -1), (1, 0), (1, 1),
           (0, 1), (-1, 1), (-1, 0), (-1, -1))  # N NE E SE S SW W NW
QUADRANTS = ("nw", "ne", "sw", "se")
# For each quadrant: two edge-adjacent neighbors and the shared diagonal.
QUAD_NEIGHBORS = ((0, 6, 7), (0, 2, 1), (4, 6, 5), (4, 2, 3))
TILE_SIZE = 64
QUARTER_SIZE = TILE_SIZE // 2


@dataclass(frozen=True)
class QuarterOverlay:
    material: str
    mask: int  # 1: horizontal outer edge, 2: vertical outer edge, 4: corner


def _surface(tile):
    surface = tile.get("surface", "grass") if tile else "grass"
    return surface if surface in MATERIALS else "grass"


def tile_key(tiles, x, y):
    """Compact, bounded key for one material, eight neighbors, and a variant.

    'tiles' is the indexed R3 scene dictionary {(x, y): tile}. A different
    height or absent neighbor is treated as the central material, preventing
    terrain painting across cliff edges or beyond the map boundary.
    """
    tile = tiles.get((x, y))
    if tile is None:
        raise ValueError("No tile at location")
    center = _surface(tile)
    height = tile.get("height", 0)
    surrounding = []
    for dx, dy in OFFSETS:
        neighbor = tiles.get((x + dx, y + dy))
        surface = (_surface(neighbor)
                   if neighbor is not None and neighbor.get("height", 0) == height
                   else center)
        surrounding.append(surface)
    variant = ((x * 17 + y * 29) & 1)
    return encode_key(center, surrounding, variant)


def encode_key(center, surrounding, variant=0):
    if (center not in MATERIALS or len(surrounding) != 8 or
            any(name not in MATERIALS for name in surrounding) or
            type(variant) is not int or variant not in (0, 1)):
        raise ValueError("Invalid quarter-autotile neighborhood")
    return "".join(str(MATERIALS.index(s)) for s in
                   (center, *surrounding)) + str(variant)


def decode_key(key):
    if not (isinstance(key, str) and len(key) == 10 and
            all(ch in "01234567" for ch in key[:9]) and key[9] in "01"):
        raise ValueError("Invalid quarter-autotile key")
    names = tuple(MATERIALS[int(d)] for d in key[:9])
    return names[0], names[1:], int(key[9])


def quadrant_overlays(center, surrounding):
    """Four ordered overlay stacks, preserving mixed-material three-way joins.

    For a quadrant, first adjacent direction maps to bit 1, second to bit 2
    and the diagonal to bit 4. Only *higher-priority land* covers the base
    material. Water and bridges keep their dedicated shoreline/bridge logic.
    The overlays are painter-sorted by priority; no tactical state changes.
    """
    if center not in MATERIALS or len(surrounding) != 8:
        raise ValueError("Invalid autotile materials")
    base_priority = LAND_PRIORITY.get(center)
    if base_priority is None:
        return ((), (), (), ())
    result = []
    for indexes in QUAD_NEIGHBORS:
        layers = {}
        for bit, idx in zip((1, 2, 4), indexes):
            incoming = surrounding[idx]
            priority = LAND_PRIORITY.get(incoming, 0)
            if priority > base_priority:
                layers[incoming] = layers.get(incoming, 0) | bit
        result.append(tuple(QuarterOverlay(material, mask) for material, mask in
                            sorted(layers.items(),
                                   key=lambda entry: (LAND_PRIORITY[entry[0]], entry[0]))))
    return tuple(result)


def overlays_for_key(key):
    center, neighbors, _ = decode_key(key)
    return quadrant_overlays(center, neighbors)


def affected_cells(changed, width, height):
    """One-tile Chebyshev halo for 8-neighbor invalidation (including diagonals)."""
    return frozenset((x + dx, y + dy)
                     for x, y in changed
                     for dx in (-1, 0, 1)
                     for dy in (-1, 0, 1)
                     if 0 <= x + dx < width and 0 <= y + dy < height)


def mask_alpha(quadrant, bits, local_x, local_y):
    """Deterministic 0..255 alpha; opaque on matching shared tile edges.

    Mask is reusable for all materials; it never encodes tactical collision.
    """
    if (quadrant not in QUADRANTS or type(bits) is not int or
            not 0 <= bits <= 7 or
            type(local_x) is not int or type(local_y) is not int or
            not 0 <= local_x < QUARTER_SIZE or
            not 0 <= local_y < QUARTER_SIZE):
        raise ValueError("Invalid autotile mask sample")
    if not bits:
        return 0
    horizontal = local_y if quadrant in ("nw", "ne") else (QUARTER_SIZE - 1 - local_y)
    vertical = local_x if quadrant in ("nw", "sw") else (QUARTER_SIZE - 1 - local_x)
    # No randomness: mirrored quadrant edges share pixel-perfect samples.
    band = 11
    alpha = max((band - horizontal) / band if bits & 1 else 0,
                (band - vertical) / band if bits & 2 else 0)
    if bits & 4:
        # Diagonal neighbor alone rounds into the tile corner.
        alpha = max(alpha, (12 - (horizontal * horizontal +
                                  vertical * vertical) ** 0.5) / 12)
    return max(0, min(255, round(255 * alpha)))


__all__ = ["MATERIALS", "OFFSETS", "QUADRANTS", "QuarterOverlay",
           "tile_key", "encode_key", "decode_key", "quadrant_overlays",
           "overlays_for_key", "affected_cells", "mask_alpha"]
