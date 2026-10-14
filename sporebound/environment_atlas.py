"""3.7.32J — deterministic, watercolor-style eight-frame environment sprite sheets.

Raster art is generated as transparent 64px RGBA frames in horizontal PNG
strips. All frames keep exactly the same dimensions and foot/canopy pivots.
No Pillow, Tk, global RNG, network or Content serialization is required.
"""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path
import struct
import zlib

from .terrain_watercolor import _chunk, _hash

KINDS = ('grass', 'reeds', 'leaves', 'water')
FRAME_SIZE = 64
FRAME_COUNT = 8
# Pivot measured in source pixels, stable in all animation frames.
PIVOTS = {'grass': (32, 54), 'reeds': (32, 54),
          'leaves': (32, 32), 'water': (32, 32)}
SWAY = (0, 1, 2, 1, 0, -1, -2, -1)
RIPPLE = (0, 1, 2, 3, 3, 2, 1, 0)

# A small hand-picked watercolor palette: pale dry brush highlights and
# transparent pigment underpainting, rather than a monochrome vector glyph.
PALETTE = {
    'grass': ((93, 132, 84), (156, 168, 95), (199, 189, 123)),
    'reeds': ((82, 122, 88), (167, 171, 109), (155, 117, 82)),
    'leaves': ((77, 117, 79), (133, 166, 98), (189, 187, 114)),
    'water': ((73, 154, 178), (144, 197, 199), (202, 225, 206)),
}


def _line_distance(px, py, x0, y0, x1, y1):
    dx, dy = x1-x0, y1-y0
    denom = dx*dx + dy*dy
    t = max(0., min(1., ((px-x0)*dx+(py-y0)*dy)/denom)) if denom else 0.
    return math.hypot(px-(x0+t*dx), py-(y0+t*dy)), t


def _elements(kind, frame):
    """Fixed planting points; only the upper free portions move."""
    wind = SWAY[frame]
    wave = RIPPLE[frame]
    shapes = []
    if kind == 'grass':
        for i, (x, height, lean) in enumerate((
                (21, 21, -6), (27, 26, -3), (32, 31, 0),
                (37, 24, 5), (44, 19, 7))):
            bottom = 54
            bend = wind*(2.0 + i%2)
            tip_x = x + lean + bend
            mid = (x + lean*.34 + bend*.26, bottom-height*.49)
            color = PALETTE[kind][i%3]
            shapes.extend((
                ('line', (x, bottom, *mid), 2.3, color, .83),
                ('line', (*mid, tip_x, bottom-height), 1.25, color, .85),
            ))
        shapes.append(('ellipse', (32, 53, 9, 2.4), 0,
                       PALETTE[kind][0], .38))
    elif kind == 'reeds':
        for i, (x, height) in enumerate(((21, 28), (29, 39), (37, 34), (45, 27))):
            tip = x + wind*(1.5+i*.25)
            mid = x + wind*.32
            end_y = 54-height
            color = PALETTE[kind][i%2]
            shapes.extend((
                ('line', (x, 54, mid, 54-height*.55), 1.9, color, .92),
                ('line', (mid, 54-height*.55, tip, end_y), 1.15, color, .9),
                ('ellipse', (tip, end_y+4, 2.4, 5.2), 0,
                 PALETTE[kind][2], .81),
                ('line', (x, 47, x-6+wind*.5, 39-i), 1.7,
                 PALETTE[kind][1], .65),
            ))
    elif kind == 'leaves':
        for i, (x, y, rx, ry) in enumerate((
                (19, 27, 9, 4.5), (29, 20, 11, 6),
                (39, 27, 11, 5.5), (32, 35, 9, 4),
                (47, 34, 7, 3.5))):
            dx = wind * (i%3+1)*.63
            dy = (frame%3-1) * .35
            shapes.append(('ellipse', (x+dx, y+dy, rx, ry), 0,
                           PALETTE[kind][i%3], .28 if i%2 else .39))
        # Central anchor stays constant to avoid crawling over the base prop.
        shapes.append(('ellipse', (32, 32, 2.2, 2.2), 0,
                       PALETTE[kind][0], .35))
    elif kind == 'water':
        for i in range(3):
            rx = 10 + i*8 + wave*.7
            ry = 3.4 + i*2.5 + wave*.23
            shapes.append(('ring', (32, 32, rx, ry), 1.5,
                           PALETTE[kind][(i+frame//3)%3], .30+i*.08))
    return tuple(shapes)


def _coverage(shape, px, py):
    name, (x, y, a, b), width, _, _ = shape
    if name == 'line':
        d, _ = _line_distance(px, py, x, y, a, b)
        return max(0., min(1., width/2 + .75-d))
    if name == 'ellipse':
        normalized = math.hypot((px-x)/a, (py-y)/b)
        return max(0., min(1., (1.08-normalized)*5))
    # Isometric water rings: thin, transparent elliptical segments.
    normalized = math.hypot((px-x)/a, (py-y)/b)
    return max(0., min(1., (width/max(a,b))*2.7 -
                             abs(normalized-1)*2.3))


def frame_rgba(kind, frame):
    """One immutable 64×64 frame with painterly pigment and transparent edges."""
    if kind not in KINDS or type(frame) is not int or not 0 <= frame < FRAME_COUNT:
        raise ValueError('Invalid environment atlas kind/frame')
    shapes = _elements(kind, frame)
    pixels = bytearray(FRAME_SIZE*FRAME_SIZE*4)
    seed = KINDS.index(kind)*947
    for y in range(FRAME_SIZE):
        for x in range(FRAME_SIZE):
            # Premultiplied-over accumulation; explicit white watercolor wash
            # is avoided so the stamps stay correct on every terrain surface.
            r = g = b = a = 0.
            for idx, shape in enumerate(shapes):
                strength = _coverage(shape, x+.5, y+.5)
                if strength <= 0:
                    continue
                color = shape[3]
                fleck = (_hash(x, y, seed+idx*41) % 31 - 15) / 255.
                opacity = max(0., min(1., strength*shape[4]*(1+fleck)))
                # Standard straight-alpha over.
                added = opacity*(1-a)
                r += color[0]*added
                g += color[1]*added
                b += color[2]*added
                a += added
            if a:
                off = (y*FRAME_SIZE+x)*4
                pixels[off:off+4] = bytes((
                    round(r/a), round(g/a), round(b/a),
                    round(255*a)))
    return bytes(pixels)


@lru_cache(maxsize=4)
def environment_strip_png(kind):
    """64 high, 8×64 wide RGBA strip; no per-frame files or runtime drawing."""
    if kind not in KINDS:
        raise ValueError('Unknown environment material')
    frames = tuple(frame_rgba(kind, i) for i in range(FRAME_COUNT))
    width = FRAME_SIZE*FRAME_COUNT
    stride = FRAME_SIZE*4
    raw = bytearray()
    for y in range(FRAME_SIZE):
        raw.append(0)
        for f in frames:
            raw.extend(f[y*stride:(y+1)*stride])
    return (b'\x89PNG\r\n\x1a\n' +
            _chunk(b'IHDR', struct.pack('>IIBBBBB', width, FRAME_SIZE,
                                       8, 6, 0, 0, 0)) +
            _chunk(b'IDAT', zlib.compress(bytes(raw), 9)) +
            _chunk(b'IEND', b''))


def export_atlases(folder):
    """Four canonical PNG strips + JSON manifest for review/QA provenance."""
    root = Path(folder)
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        'version': 1, 'frame_size': [FRAME_SIZE, FRAME_SIZE],
        'frames': FRAME_COUNT, 'frame_duration_ms': 125,
        'materials': {},
    }
    for kind in KINDS:
        output = root / (kind+'.png')
        data = environment_strip_png(kind)
        output.write_bytes(data)
        manifest['materials'][kind] = {
            'file': output.name, 'sha256': sha256(data).hexdigest(),
            'pivot': list(PIVOTS[kind]), 'size': [FRAME_SIZE*FRAME_COUNT, FRAME_SIZE],
        }
    path = root / 'manifest.json'
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n',
                    encoding='utf-8')
    return manifest


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    manifest = export_atlases(args.output_dir)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
