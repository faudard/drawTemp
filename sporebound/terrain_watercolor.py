"""3.7.32G — dependency-free, reproducible watercolor terrain material atlas.

Painted-looking pigment washes with edge-safe diamonds; no downloads, Pillow,
Tk, RNG state or binary asset authoring format. The 8x2 tile contract remains
96x48 pixels and is compatible with the legacy IsoTerrainAtlas crop path.
"""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import struct
import zlib

MATERIALS = ('grass', 'dirt', 'stone', 'cobble', 'sand', 'rock', 'water', 'bridge')
TILE_WIDTH, TILE_HEIGHT, VARIANTS = 96, 48, 2
# Slightly desaturated pigments reproduce the established watercolor palette.
PIGMENTS = {
    'grass': (153, 166, 108), 'dirt': (198, 168, 117),
    'stone': (172, 166, 154), 'cobble': (198, 185, 160),
    'sand': (222, 200, 151), 'rock': (142, 151, 141),
    'water': (77, 146, 172), 'bridge': (197, 180, 150),
}
# Brush-stroke highlight / pigment shadows: each material uses independent
# natural tones rather than a uniform grayscale-noise multiplication.
WASHES = {
    'grass': ((206, 198, 116), (81, 116, 75)),
    'dirt': ((241, 210, 158), (141, 107, 76)),
    'stone': ((222, 211, 189), (116, 122, 116)),
    'cobble': ((230, 216, 188), (135, 130, 116)),
    'sand': ((250, 226, 174), (180, 153, 110)),
    'rock': ((195, 187, 166), (100, 115, 114)),
    'water': ((153, 195, 191), (37, 111, 148)),
    'bridge': ((231, 212, 164), (134, 118, 94)),
}


def _hash(x, y, seed):
    """Stable arithmetic hash, portable across Python versions and processes."""
    v = (((x & 0xffffffff) * 0x9e3779b1) ^
         ((y & 0xffffffff) * 0x85ebca77) ^
         ((seed & 0xffffffff) * 0xc2b2ae3d)) & 0xffffffff
    v ^= v >> 16
    v = v * 0x7feb352d & 0xffffffff
    v ^= v >> 15
    v = v * 0x846ca68b & 0xffffffff
    return (v ^ (v >> 16)) & 0xffffffff


def _noise(x, y, scale, seed):
    gx, gy = x // scale, y // scale
    fx, fy = (x % scale) / scale, (y % scale) / scale
    fx, fy = fx * fx * (3 - 2*fx), fy * fy * (3 - 2*fy)
    a = _hash(gx, gy, seed) / 0xffffffff
    b = _hash(gx+1, gy, seed) / 0xffffffff
    c = _hash(gx, gy+1, seed) / 0xffffffff
    d = _hash(gx+1, gy+1, seed) / 0xffffffff
    return ((a*(1-fx) + b*fx)*(1-fy) +
            (c*(1-fx) + d*fx)*fy)


def _blend(a, b, weight):
    return tuple(max(0, min(255, round(v*(1-weight)+w*weight)))
                 for v, w in zip(a, b))


def pixel(material, variant, x, y):
    """One RGBA pixel; opaque pixels at matching edge share identical pigment.

    Edge-safe design: for each material the outer ~3-5px fade to one common
    base pigment *irrespective of variant*. Adjacent diamonds cannot develop
    bright double-border streaks. Cliff sides remain a separate render layer.
    """
    if material not in PIGMENTS or type(variant) is not int or variant not in (0, 1):
        raise ValueError('Unknown watercolor material or variant')
    if not (0 <= x < TILE_WIDTH and 0 <= y < TILE_HEIGHT):
        raise ValueError('Pixel outside watercolor tile')
    distance = (abs(x+.5-TILE_WIDTH/2)/(TILE_WIDTH/2) +
                abs(y+.5-TILE_HEIGHT/2)/(TILE_HEIGHT/2))
    if distance >= 1:
        return 0, 0, 0, 0
    seed = MATERIALS.index(material)*31337 + variant*13579 + 17
    coarse = _noise(x, y, 17, seed)
    medium = _noise(x, y, 7, seed ^ 0x52e125)
    granule = _hash(x, y, seed ^ 0x9e74) / 0xffffffff
    tone = .64*coarse+.29*medium+.07*granule
    base = PIGMENTS[material]
    highlight, shade = WASHES[material]
    candidate = (_blend(base, highlight, min(.44, max(0, tone-.47)*1.8))
                 if tone >= .47 else
                 _blend(base, shade, min(.44, (.47-tone)*1.4)))
    # Small, sparse leaf/stone/watergrain flecks. Keep them under the
    # translucent watercolor wash rather than cartoonishly outlining dots.
    speckle = _hash(x//2, y//2, seed ^ 0xc351) % 97
    if speckle in (0, 1, 2):
        amount = .18 if material != 'water' else .28
        candidate = _blend(candidate, highlight, amount)
    # Identical pigment precisely along shared perimeter across both variants.
    strength = min(1., max(0., (1.-distance)*9.))
    strength = strength*strength*(3-2*strength)
    return (*_blend(base, candidate, strength), 255)


def _chunk(kind, content):
    return (struct.pack('>I', len(content)) + kind + content +
            struct.pack('>I', zlib.crc32(kind + content) & 0xffffffff))


@lru_cache(maxsize=1)
def watercolor_atlas_png():
    """Build a complete, valid RGBA PNG atlas with standard-library zlib."""
    width = len(MATERIALS)*VARIANTS*TILE_WIDTH
    height = TILE_HEIGHT
    image = bytearray()
    for y in range(height):
        image.append(0)  # PNG scanline filter None
        for material in MATERIALS:
            for variant in range(VARIANTS):
                for x in range(TILE_WIDTH):
                    image.extend(pixel(material, variant, x, y))
    header = (b'\x89PNG\r\n\x1a\n' +
              _chunk(b'IHDR', struct.pack('>IIBBBBB', width, height,
                                          8, 6, 0, 0, 0)))
    return header + _chunk(b'IDAT', zlib.compress(bytes(image), 9)) + _chunk(b'IEND', b'')


def watercolor_atlas_sha256():
    return sha256(watercolor_atlas_png()).hexdigest()


def write_watercolor_atlas(path):
    """Export a reproducible PNG for artist review without altering packages."""
    from pathlib import Path
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = watercolor_atlas_png()
    path.write_bytes(data)
    return {'path': str(path), 'sha256': sha256(data).hexdigest(),
            'width': len(MATERIALS)*VARIANTS*TILE_WIDTH, 'height': TILE_HEIGHT,
            'bytes': len(data)}


def main(argv=None):
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    print(json.dumps(write_watercolor_atlas(args.output), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
