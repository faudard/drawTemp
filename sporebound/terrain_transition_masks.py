"""3.7.32H — watercolor feather masks along neighbouring isometric terrain.

Transparent directional PNG stamps, drawn over the same watercolor atlas used
by the Studio and Player. Masks are generated on demand per material, direction
and four stable variants: 6 terrestrial materials × 4 directions × 4 variants.
There is no map format, third-party image decoder, RNG state or per-cell PNG.
"""
from __future__ import annotations

from functools import lru_cache
import struct
import zlib

from .iso_connections import N, E, S, W
from .terrain_autoblend import LAND_PRIORITY
from .terrain_watercolor import (
    PIGMENTS, WASHES, TILE_WIDTH, TILE_HEIGHT, _hash, _noise, _blend, _chunk,
)

DIRECTIONS = (N, E, S, W)
MASK_VARIANTS = 4


def _edge_distance(bit, u, v):
    """Distance from pixel to one diamond edge in normalized iso geometry.

    The assignment agrees exactly with iso_connections.transition_segments:
    N: west→north, E: east→south, S: south→west, W: north→east.
    """
    if bit == N:
        return 1 + u + v
    if bit == E:
        return 1 - u - v
    if bit == S:
        return 1 + u - v
    if bit == W:
        return 1 - u + v
    raise ValueError('Unsupported transition mask direction')


def painted_mask_pixel(material, bit, variant, x, y):
    """RGBA sampled in native 96×48 tile coordinates.

    At the shared edge, the mask is fully opaque and matches the neighbour's
    base pigment exactly (its atlas colors also converge to base at the rim).
    Away from the edge the wash feathers into transparency, with low-frequency
    painterly fluctuations but no harsh tiling grid or clipped neighboring art.
    """
    if material not in LAND_PRIORITY or bit not in DIRECTIONS:
        raise ValueError('Unsupported painted transition material or direction')
    if type(variant) is not int or not 0 <= variant < MASK_VARIANTS:
        raise ValueError('Unsupported painted transition variant')
    if type(x) is not int or type(y) is not int or not (
            0 <= x < TILE_WIDTH and 0 <= y < TILE_HEIGHT):
        raise ValueError('Painted transition pixel out of range')

    u = (x + .5 - TILE_WIDTH/2) / (TILE_WIDTH/2)
    v = (y + .5 - TILE_HEIGHT/2) / (TILE_HEIGHT/2)
    if abs(u) + abs(v) >= 1:
        return (0, 0, 0, 0)
    distance = _edge_distance(bit, u, v)
    if distance < 0:
        return (0, 0, 0, 0)

    # An unchanged boundary guarantees the same pigment as its adjacent tile;
    # irregularity starts *inside* the receiving surface, never on the edge.
    base = PIGMENTS[material]
    if distance <= .085:
        return (*base, 255)

    seed = (PIGMENTS[material][0] * 1949 +
            bit * 2927 + variant * 13763)
    wobble = (_noise(x + 47, y + 13, 13, seed) - .5) * .10
    # Nominal wash thickness varies from 6px to 10px according to face angle.
    width = .23 + wobble
    if distance >= width:
        return (0, 0, 0, 0)
    t = max(0., min(1., (width - distance)/(width-.085)))
    feather = t*t*(3-2*t)
    # Transparent bleeding/pigment granules use reproducible microtexturing.
    flecks = (_hash(x // 2, y // 2, seed ^ 0x4931) % 13) / 12
    opacity = max(1, min(255, round(255 * feather*(.88 + .12*flecks))))
    bloom = (_noise(x, y, 6, seed ^ 0x3547) - .5)*.12
    if bloom > 0:
        color = _blend(base, WASHES[material][0], bloom)
    else:
        color = _blend(base, WASHES[material][1], -bloom)
    return (*color, opacity)


@lru_cache(maxsize=128)
def painted_mask_png(material, bit, variant=0):
    """Return compact, valid RGBA PNG bytes for a reusable transition stamp."""
    if material not in LAND_PRIORITY or bit not in DIRECTIONS or (
            type(variant) is not int or not 0 <= variant < MASK_VARIANTS):
        raise ValueError('Invalid painted mask specification')
    rows = bytearray()
    for y in range(TILE_HEIGHT):
        rows.append(0)
        for x in range(TILE_WIDTH):
            rows.extend(painted_mask_pixel(material, bit, variant, x, y))
    return (b'\x89PNG\r\n\x1a\n' +
            _chunk(b'IHDR', struct.pack('>IIBBBBB', TILE_WIDTH, TILE_HEIGHT,
                                         8, 6, 0, 0, 0)) +
            _chunk(b'IDAT', zlib.compress(bytes(rows), 9)) +
            _chunk(b'IEND', b''))


def painted_mask_key(blend):
    """Stable, shared brush key independent of viewport and render order."""
    return (blend.incoming, blend.bit, blend.pattern % MASK_VARIANTS)


def ordered_blend_masks(edges, priorities):
    """Lower priority first; strongest paint owns multi-material corners.

    A 3-material corner is unambiguous: the highest-priority incoming
    material is composited last, irrespective of original direction order.
    """
    return tuple(sorted(edges, key=lambda edge: (
        priorities[edge.incoming], edge.bit, edge.pattern % MASK_VARIANTS)))


def main(argv=None):
    """Write a contact-sheet of mask swatches for art QA."""
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    directory = Path(args.output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    count = 0
    for material in LAND_PRIORITY:
        for bit, tag in ((N, 'n'), (E, 'e'), (S, 's'), (W, 'w')):
            dest = directory / f'{material}_{tag}.png'
            dest.write_bytes(painted_mask_png(material, bit))
            count += 1
    print(f'{count} directional RGBA masks exported to {directory}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
