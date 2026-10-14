"""3.7.32I — time-driven isometric terrain ambience, not tactical state.

Decorative swaying grass/reeds/leaves and quiet water ripples are Canvas
primitives owned by the same per-tile render groups as ordinary terrain.
This module is Tk-free until a caller supplies a Canvas; the game engine,
Content JSON, replays, motion CT, collision, and saves never see clock time.
"""
from __future__ import annotations

from dataclasses import dataclass

from .terrain_watercolor import _hash
from .environment_atlas import FRAME_COUNT, PIVOTS

TICK_MS = 125
MAX_ANIMATED_CELLS = 256
SWAY = (0, 1, 2, 1, 0, -1, -2, -1)
RIPPLE = (0, 1, 2, 3, 3, 2, 1, 0)


@dataclass(frozen=True)
class AmbientStroke:
    kind: str
    cell: tuple
    part: int
    shape: str
    coords: tuple
    color: str


def _eligible(board, cell, kind):
    """Bound Canvas item count on 128² worlds; never depend on viewport."""
    area = board.width * board.height
    # Even a full water/grass world adds at most ~256 eligible cells,
    # independent of zoom, rendering order, or source file layout.
    divisor = max(1, (area + MAX_ANIMATED_CELLS - 1) // MAX_ANIMATED_CELLS)
    base = {'grass': 5, 'water': 4, 'reeds': 1, 'leaves': 1}[kind]
    return _hash(cell[0], cell[1], 0x73ed + len(kind)) % (base * divisor) == 0


def ambient_kind(board, cell):
    """The one authoritative authoring-to-ambience mapping (no new tile data)."""
    if not board.contains(cell):
        return None
    tile = board.tile(cell)
    if tile.surface == 'water':
        kind = 'water'
    elif tile.feature == 'reeds':
        kind = 'reeds'
    elif tile.feature in ('tree', 'bush'):
        kind = 'leaves'
    elif tile.surface == 'grass' and not tile.feature:
        kind = 'grass'
    else:
        return None
    return kind if _eligible(board, cell, kind) else None


def sprite_origin(board, cell, center, size):
    """Top-left of a 64px raster sheet with an invariant world-space pivot."""
    kind = ambient_kind(board, cell)
    if kind is None:
        return None
    cx, cy = center
    seed = _hash(*cell, 0xdead)
    cx += ((seed % 13) - 6) * size / 55
    cy += (((seed >> 5) % 7) - 3) * size / 95
    if kind == 'leaves':
        cy -= size * (.8 if board.tile(cell).feature == 'tree' else .3)
    scaled = max(1, round(64 * size / 54))
    ratio = scaled / 64
    px, py = PIVOTS[kind]
    return (cx-px*ratio, cy-py*ratio)


def sprite_tag(kind, cell):
    """Unique stable marker consumed by both retained and full Canvas paths."""
    return f'iso_env_frame_{kind}_{cell[0]}_{cell[1]}'


def sprite_phase(kind, cell, clock_ms):
    """Raster frame sampling shares the ambient UI clock; no gameplay turns."""
    if kind not in ('grass', 'reeds', 'leaves', 'water'):
        raise ValueError('Unknown environment kind')
    if type(clock_ms) not in (int, float) or clock_ms < 0:
        raise ValueError('Nonnegative presentation clock required')
    return ((int(clock_ms) // TICK_MS) +
            _hash(cell[0], cell[1], 0x2718) % FRAME_COUNT) % FRAME_COUNT


def strokes_for_cell(board, cell, center, size, *, enabled=True):
    """Deterministic small foreground accents from *existing* tile values.

    Accent strokes belong inside the tile group for depth sorting, dirty-tile
    invalidation, and cutaway/zoom parity. Nothing is added to Content.
    """
    if not enabled:
        return ()
    kind = ambient_kind(board, cell)
    if kind is None:
        return ()
    cx, cy = center
    seed = _hash(*cell, 0xdead)
    dx = ((seed % 13) - 6) * size / 55
    dy = (((seed >> 5) % 7) - 3) * size / 95
    cx, cy = cx + dx, cy + dy
    h = max(2, size / 12)
    if kind == 'water':
        w, t = size * .19, size * .065
        return (
            AmbientStroke('water', cell, 0, 'oval',
                          (cx-w, cy-t, cx+w, cy+t), '#b8dddd'),
        )
    if kind == 'grass':
        return (
            AmbientStroke(kind, cell, 0, 'line',
                          (cx, cy, cx-size*.047, cy-h), '#718d58'),
            AmbientStroke(kind, cell, 1, 'line',
                          (cx+size*.035, cy, cx+size*.065, cy-h*.85), '#c4bd78'),
        )
    if kind == 'reeds':
        return tuple(AmbientStroke(kind, cell, part, 'line',
                     (cx+(part-1)*size*.065, cy,
                      cx+(part-1)*size*.082, cy-max(4, size*.22) +
                      part*size*.02), '#879968' if part != 1 else '#bea879')
                     for part in range(3))
    # Leaves flutter close to the projected base of a tree/bush. Existing
    # prop sprite remains the primary artwork, never replaced or stretched.
    return (
        AmbientStroke('leaves', cell, 0, 'line',
                      (cx-size*.2, cy-size*.34, cx-size*.12, cy-size*.36),
                      '#819d71'),
        AmbientStroke('leaves', cell, 1, 'line',
                      (cx+size*.1, cy-size*.31, cx+size*.18, cy-size*.34),
                      '#b2b66c'),
    )


def phase_index(stroke, clock_ms):
    """Integer animation clock; same cell+seed+time always yields same pose."""
    if type(clock_ms) not in (int, float) or clock_ms < 0:
        raise ValueError('Nonnegative presentation clock required')
    x, y = stroke.cell
    return (int(clock_ms) // TICK_MS +
            _hash(x, y, stroke.part*1009) % len(SWAY)) % len(SWAY)


def animated_coords(stroke, clock_ms):
    """Use initial coordinates, not coordinates from the previous frame."""
    base = stroke.coords
    step = phase_index(stroke, clock_ms)
    if stroke.kind == 'water':
        x0, y0, x1, y1 = base
        cx, cy = (x0+x1)/2, (y0+y1)/2
        scale = 1 + RIPPLE[step] * .08
        return (cx+(x0-cx)*scale, cy+(y0-cy)*scale,
                cx+(x1-cx)*scale, cy+(y1-cy)*scale)
    x0, y0, x1, y1 = base
    height = max(1., abs(y1-y0))
    amplitude = min(4., height*.34)
    direction = -1 if stroke.part % 2 else 1
    offset = SWAY[step] * amplitude * direction / 2
    # Preserve planted base; deform only the free leaf/stalk tip.
    return (x0, y0, x1+offset, y1)


def stroke_tag(stroke):
    x, y = stroke.cell
    return f'iso_ambient_{stroke.kind}_{x}_{y}_{stroke.part}'


class TerrainAmbientAnimator:
    """Tick existing Canvas items in place; NEVER re-render battle/terrain.

    capture() is called only after full/delta renderer synchronization.
    restore() resets motion before EditorRenderCache diffs, so retained
    commands remain authoritative and repeated refreshes cannot accumulate
    offset. No Tk timers are owned here: the hosting UI cancels its job.
    """

    def __init__(self):
        self.items = {}
        self.sprites = {}
        self._last_tick = None

    def capture(self, canvas):
        self.items.clear()
        self.sprites.clear()
        self._last_tick = None
        if not all(hasattr(canvas, n) for n in
                   ('find_withtag', 'gettags', 'coords', 'type')):
            return 0
        for item in canvas.find_withtag('iso_ambient'):
            frame_tags = [tag for tag in canvas.gettags(item)
                          if tag.startswith('iso_env_frame_')]
            if len(frame_tags) == 1 and canvas.type(item) == 'image':
                parts = frame_tags[0].split('_')
                if len(parts) == 6 and parts[3] in (
                        'grass', 'reeds', 'leaves', 'water'):
                    try:
                        cell = (int(parts[4]), int(parts[5]))
                        baseline = canvas.itemcget(item, 'image')
                    except (TypeError, ValueError, AttributeError):
                        continue
                    self.sprites[item] = (parts[3], cell, baseline)
                continue
            names = [tag for tag in canvas.gettags(item)
                     if tag.startswith('iso_ambient_') and tag != 'iso_ambient']
            if len(names) != 1:
                continue
            fields = names[0].split('_')
            if len(fields) != 6 or fields[2] not in (
                    'water', 'grass', 'reeds', 'leaves'):
                continue
            try:
                x, y, part = map(int, fields[3:])
                coords = tuple(canvas.coords(item))
            except (TypeError, ValueError):
                continue
            kind = fields[2]
            shape = 'oval' if kind == 'water' else 'line'
            if canvas.type(item) != shape or len(coords) != 4:
                continue
            self.items[item] = AmbientStroke(
                kind, (x, y), part, shape, coords, '')
        return len(self.items) + len(self.sprites)

    def restore(self, canvas):
        for item, stroke in self.items.items():
            canvas.coords(item, *stroke.coords)
        for item, (_, _, baseline) in self.sprites.items():
            canvas.itemconfigure(item, image=baseline)
        self._last_tick = None

    def tick(self, canvas, clock_ms, *, atlas=None, cell_size=None):
        quantized = int(clock_ms) // TICK_MS
        if self._last_tick == quantized:
            return 0
        self._last_tick = quantized
        for item, stroke in self.items.items():
            canvas.coords(item, *animated_coords(stroke, clock_ms))
        if atlas is not None and cell_size is not None:
            for item, (kind, cell, _) in self.sprites.items():
                photo = atlas.frame(kind, cell_size,
                                    sprite_phase(kind, cell, clock_ms))
                if photo is not None:
                    canvas.itemconfigure(item, image=photo)
        return len(self.items) + len(self.sprites)

    @property
    def active(self):
        return bool(self.items or self.sprites)

    def clear(self):
        self.items.clear()
        self.sprites.clear()
        self._last_tick = None
