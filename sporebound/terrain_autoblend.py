"""3.7.32F — deterministic terrain generation and neighbour-aware AutoBlend.

The tile model and authored material tokens are unchanged. Transition geometry
is presentation-only; a saved mission contains ordinary surface values.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json

from .iso_connections import DIRECTIONS, transition_segments
from .map_authoring import _mission, cells_in_rectangle
from .model import Content, require

# Only terrestrial top faces blend. Water and bridges retain their existing
# shoreline/bridge rendering; distinct elevations retain cliff outlines.
LAND_PRIORITY = {
    'sand': 1, 'dirt': 2, 'grass': 3,
    'cobble': 4, 'stone': 5, 'rock': 6,
}
REGION_STYLES = ('prairie', 'aride', 'rocaille', 'bocage', 'lande', 'vallon')
LAND_COLORS = {
    'grass': '#9aa66c', 'dirt': '#c6a875', 'sand': '#dec897',
    'stone': '#aca69a', 'cobble': '#c6b9a0', 'rock': '#8e978d',
}
_MAX_REGION = 4096


def _hash(x, y, seed=0):
    """Portable 32-bit integer mixer (not Python's randomized hash())."""
    n = ((x & 0xffffffff) * 0x9e3779b1 ^
         (y & 0xffffffff) * 0x85ebca77 ^
         (seed & 0xffffffff) * 0xc2b2ae3d) & 0xffffffff
    n ^= n >> 16
    n = (n * 0x7feb352d) & 0xffffffff
    n ^= n >> 15
    n = (n * 0x846ca68b) & 0xffffffff
    return (n ^ (n >> 16)) & 0xffffffff


def _noise(x, y, seed, scale):
    """Smooth value noise sampled at *world* coordinates, never tile-local."""
    gx, gy = x // scale, y // scale
    tx, ty = (x % scale) / scale, (y % scale) / scale
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    v = lambda a, b: _hash(a, b, seed) / 0xffffffff
    a = v(gx, gy) * (1-tx) + v(gx+1, gy) * tx
    b = v(gx, gy+1) * (1-tx) + v(gx+1, gy+1) * tx
    return a * (1-ty) + b * ty


def _biome_surface(x, y, seed, style):
    """Domain-warped moisture/relief fields create organic *world-space* patches.

    The sampling never depends on the requested rectangle: adjacent batches
    produce the same landscape, including over negative test coordinates.
    Existing F-style generation is kept byte-for-byte compatible.
    """
    wx = x + round((_noise(x, y, seed ^ 0x1a54, 17) - .5) * 12)
    wy = y + round((_noise(x, y, seed ^ 0x932b, 17) - .5) * 12)
    moisture = (.72 * _noise(wx, wy, seed ^ 0x43ea, 19) +
                .28 * _noise(wx, wy, seed ^ 0x77ab, 7))
    relief = (.64 * _noise(wx, wy, seed ^ 0x221d, 23) +
              .36 * _noise(wx, wy, seed ^ 0x70f5, 6))
    if style == 'bocage':
        # Meadow with sinuous dirt paths and occasional exposed stone.
        trail = abs(_noise(wx, wy, seed ^ 0xabc5, 26) - .51)
        return ('stone' if relief > .68 else
                'dirt' if trail < .060 or moisture < .34 else 'grass')
    if style == 'lande':
        # Upland heath: stony outcrops, earth and intermittent green pockets.
        return ('rock' if relief > .59 else
                'stone' if relief > .48 else
                'grass' if moisture > .52 else 'dirt')
    # Vallon: generous meadow floor, damp earth and sparse gravel banks.
    return ('stone' if relief > .73 else
            'sand' if moisture < .30 else
            'dirt' if moisture < .44 else 'grass')


def biome_feature_at(x, y, *, seed=0, style='bocage', surface='grass',
                     vegetation=0, near_water=False):
    """Opt-in *presentation-only* flora using existing prop sprites.

    No tile collision, movement cost, tactical cover or water is generated.
    Values are absolute-coordinate deterministic, not dependant on selection
    order or the Python RNG state.
    """
    require(type(vegetation) is int and 0 <= vegetation <= 3,
            'Vegetation density must be 0..3')
    require(style in REGION_STYLES, 'Unknown terrain style')
    if not vegetation or surface not in ('grass', 'dirt', 'stone', 'rock'):
        return ''
    sample = _hash(x, y, seed ^ 0x4b10) / 0xffffffff
    patch = .65 + .75 * _noise(x, y, seed ^ 0x8c81, 9)
    amount = vegetation * .022 * patch
    if near_water and surface == 'grass' and sample < vegetation * .085:
        return 'reeds'
    if surface == 'grass':
        tree_weight = 1.25 if style in ('bocage', 'vallon') else .55
        if sample < amount * tree_weight:
            return 'tree'
        if sample < amount * (tree_weight + 2.4):
            return 'bush'
    elif surface in ('stone', 'rock') and sample < amount * 1.7:
        return 'boulder'
    elif surface == 'dirt' and sample < amount * .55:
        return 'bush'
    return ''


def surface_at(x, y, *, seed=0, style='prairie'):
    """A coherent region independent of generation batch, order or viewport."""
    require(type(x) is int and type(y) is int, 'Terrain coordinates must be integers')
    require(type(seed) is int and 0 <= seed <= 0x7fffffff,
            'Terrain seed must be a nonnegative 31-bit integer')
    require(style in REGION_STYLES, 'Unknown terrain style')
    if style in ('bocage', 'lande', 'vallon'):
        return _biome_surface(x, y, seed, style)
    value = (.78 * _noise(x, y, seed, 9) +
             .22 * _noise(x, y, seed ^ 0x5f3759df, 4))
    if style == 'prairie':
        return ('grass' if value < .61 else 'dirt' if value < .80 else 'stone')
    if style == 'aride':
        return ('sand' if value < .56 else 'dirt' if value < .80 else 'rock')
    return 'grass' if value < .19 else 'stone' if value < .50 else 'rock'


def terrain_variant(cell, count=2, *, seed=0):
    """Stable texture variant, without repeated vertical/diagonal stripes."""
    require(type(count) is int and 1 <= count <= 256, 'Invalid variant count')
    return _hash(cell[0], cell[1], seed) % count


@dataclass(frozen=True)
class BlendEdge:
    bit: int
    incoming: str
    pattern: int


def blend_edges(board, cell):
    """Only the lower-priority land tile receives its neighbour's edge color."""
    if not board.contains(cell):
        return ()
    tile = board.tile(cell)
    priority = LAND_PRIORITY.get(tile.surface)
    if priority is None:
        return ()
    x, y = cell
    result = []
    for dx, dy, bit in DIRECTIONS:
        adjacent = (x + dx, y + dy)
        if not board.contains(adjacent):
            continue
        other = board.tile(adjacent)
        if (other.height != tile.height or
                LAND_PRIORITY.get(other.surface, -1) <= priority):
            continue
        a, b = sorted((cell, adjacent))
        result.append(BlendEdge(bit, other.surface,
                                _hash(a[0] ^ b[0], a[1] ^ b[1],
                                      a[0] * 3571 + a[1] * 257 + bit % 2)))
    return tuple(result)


def blend_polygon(corners, edge):
    """An irregular strip INSIDE this diamond, joining the exact shared edge.

    The outer side uses the actual polygon endpoints, so the neighbour's
    material touches without introducing a gap at any camera zoom.
    """
    (first, last), = transition_segments(corners, edge.bit)
    center = (sum(p[0] for p in corners) / 4,
              sum(p[1] for p in corners) / 4)
    inner = []
    for i in range(7):
        t = i / 6
        x = first[0] * (1-t) + last[0] * t
        y = first[1] * (1-t) + last[1] * t
        # A broad central feather, narrowing at endpoints to avoid swamping
        # perpendicular shorelines and adjacent transition strips.
        offset = .10 + .10 * (1 - abs(2*t - 1))
        offset += (((edge.pattern >> (i*4 % 24)) & 15) - 7.5) / 150
        inner.append((x + (center[0] - x) * offset,
                      y + (center[1] - y) * offset))
    points = (first, last, *reversed(inner))
    return tuple(coordinate for point in points for coordinate in point)


def terrain_dependents(board, changed):
    """Bounded 4-neighbour visual invalidation; existing dirty cache uses 3×3."""
    result = set()
    for x, y in changed:
        for dx, dy in ((0, 0), *((a, b) for a, b, _ in DIRECTIONS)):
            candidate = (x + dx, y + dy)
            if board.contains(candidate):
                result.add(candidate)
    return frozenset(result)


@dataclass(frozen=True)
class TerrainPlan:
    mission_id: str
    seed: int
    style: str
    source_sha256: str
    changes: tuple  # ((x, y, material), ...), canonical row-major order
    decorations: tuple = ()  # ((x, y, feature), ...); optional, non-tactical
    vegetation: int = 0


def _fingerprint(data):
    return sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False).encode('utf-8')).hexdigest()


def plan_terrain_region(data, mission_id, start, end, *, seed=1, style='prairie',
                        vegetation=0):
    """Pure, inspectable region preview with no document or RNG mutation."""
    require(type(seed) is int and 0 <= seed <= 0x7fffffff,
            'Terrain seed must be a nonnegative 31-bit integer')
    require(style in REGION_STYLES, 'Unknown terrain style')
    require(type(vegetation) is int and 0 <= vegetation <= 3,
            'Vegetation density must be 0..3')
    mission = _mission(data, mission_id)
    cells = cells_in_rectangle(data, mission_id, start, end)
    require(len(cells) <= _MAX_REGION, 'Terrain region exceeds 4096 cells')
    tiles = {tuple(tile['pos']): tile for tile in mission['board']['tiles']}
    occupied = {tuple(u['pos']) for u in mission['units']}
    occupied.update(tuple(obj['pos']) for obj in mission['objects'])
    occupied.update(tuple(goal) for goal in mission.get('goal', ()))
    changed = []
    decorations = []
    for x, y in cells:
        old = tiles.get((x, y), {})
        # Keep authored structures, meaningful props, tactical objectives and
        # rivers untouched. Layout planning never silently removes them.
        if ((x, y) in occupied or old.get('feature') or old.get('blocked')
                or old.get('surface') in ('water', 'bridge')
                or old.get('height', 0) or old.get('hazard', 0)
                or old.get('cover', 0) or old.get('cost', 1) != 1):
            continue
        material = surface_at(x, y, seed=seed, style=style)
        if old.get('surface', 'grass') != material:
            changed.append((x, y, material))
        if vegetation:
            near_water = any(tiles.get((x + dx, y + dy), {}).get('surface') == 'water'
                             for dx, dy, _ in DIRECTIONS)
            feature = biome_feature_at(x, y, seed=seed, style=style,
                                       surface=material, vegetation=vegetation,
                                       near_water=near_water)
            if feature:
                decorations.append((x, y, feature))
    return TerrainPlan(mission_id, seed, style, _fingerprint(data),
                       tuple(changed), tuple(decorations), vegetation)


def apply_terrain_plan(data, plan):
    """All-or-nothing application through the same Content validation as paint."""
    require(isinstance(plan, TerrainPlan), 'Expected a terrain preview plan')
    require(_fingerprint(data) == plan.source_sha256,
            'Terrain preview is stale; regenerate before applying')
    require(plan.style in REGION_STYLES, 'Invalid terrain plan style')
    require(type(plan.vegetation) is int and 0 <= plan.vegetation <= 3,
            'Invalid terrain plan vegetation density')
    require(not plan.decorations or plan.vegetation > 0,
            'Decorations require an enabled density')
    mission = _mission(data, plan.mission_id)
    require(len(plan.changes) <= _MAX_REGION and
            len(plan.decorations) <= _MAX_REGION, 'Oversized terrain plan')
    if not plan.changes and not plan.decorations:
        return data
    updated = deepcopy(data)
    target = _mission(updated, plan.mission_id)
    tiles = {tuple(tile['pos']): tile for tile in target['board']['tiles']}
    original_tiles = {point: dict(tile) for point, tile in tiles.items()}
    occupied = {tuple(unit['pos']) for unit in target['units']}
    occupied.update(tuple(obj['pos']) for obj in target['objects'])
    occupied.update(tuple(goal) for goal in target.get('goal', ()))
    seen = set()
    for x, y, material in plan.changes:
        require(type(x) is int and type(y) is int and
                (x, y) not in seen and
                0 <= x < target['board']['width'] and
                0 <= y < target['board']['height'],
                'Invalid terrain plan coordinates')
        seen.add((x, y))
        require(material in LAND_PRIORITY and
                material == surface_at(x, y, seed=plan.seed,
                                       style=plan.style),
                'Invalid terrain preview material')
        old = tiles.get((x, y), {'pos': [x, y]})
        require((x, y) not in occupied and
                not old.get('feature') and not old.get('blocked') and
                not old.get('height') and not old.get('hazard') and
                not old.get('cover') and old.get('cost', 1) == 1 and
                old.get('surface') not in ('water', 'bridge'),
                'Cannot overwrite authored terrain')
        tiles[(x, y)] = {**old, 'surface': material}
    decorated = set()
    for x, y, feature in plan.decorations:
        require(type(x) is int and type(y) is int and
                0 <= x < target['board']['width'] and
                0 <= y < target['board']['height'] and (x, y) not in decorated,
                'Invalid vegetation coordinates')
        decorated.add((x, y))
        previous = original_tiles.get((x, y), {})
        tile = tiles.get((x, y), {'pos': [x, y]})
        near_water = any(
            original_tiles.get((x + dx, y + dy), {}).get('surface') == 'water'
            for dx, dy, _ in DIRECTIONS)
        expected = biome_feature_at(
            x, y, seed=plan.seed, style=plan.style,
            surface=surface_at(x, y, seed=plan.seed, style=plan.style),
            vegetation=plan.vegetation, near_water=near_water)
        require(feature == expected and bool(expected) and
                (x, y) not in occupied and not previous.get('feature') and
                not previous.get('blocked') and not previous.get('height') and
                not previous.get('hazard') and not previous.get('cover') and
                previous.get('cost', 1) == 1 and
                previous.get('surface') not in ('water', 'bridge'),
                'Invalid or protected vegetation preview')
        tiles[(x, y)] = {**tile, 'feature': feature}
    target['board']['tiles'] = list(tiles.values())
    return Content.from_dict(updated).to_dict()
