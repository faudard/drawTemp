"""3.7.32L — reproducible connected landscapes for existing tactical maps.

This is authoring, not a replacement map model. The output is ordinary
Content/Tile records rendered by the shared watercolor Studio/Player path.
No Tk, filesystem writes, random module or new save schema.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .map_authoring import _mission, cells_in_rectangle
from .model import Content, require
from .terrain_autoblend import (
    REGION_STYLES, _fingerprint, _hash, _noise, _reserved_cells,
    biome_feature_at, surface_at,
)

MAX_CELLS = 4096


@dataclass(frozen=True)
class NaturalMapPlan:
    mission_id: str
    start: tuple
    end: tuple
    seed: int
    style: str
    vegetation: int
    source_sha256: str
    # Changes are canonical (x,y,surface,height,blocked,feature) tuples.
    changes: tuple
    river: tuple
    road: tuple
    clearings: tuple

    @property
    def changed_cells(self):
        return tuple((x, y) for x, y, *_ in self.changes)


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _connected_path(bounds, seed, *, vertical):
    """One 4-connected meandering stroke crossing the region edge to edge.

    Natural bends are smoothed in world coordinates; all intermediate cells
    are retained when the transverse position moves by more than one step.
    """
    x0, y0, x1, y1 = bounds
    first, last = (y0, y1) if vertical else (x0, x1)
    lower, upper = (x0, x1) if vertical else (y0, y1)
    margin = max(2, (upper - lower) // 6)
    center = (lower + upper) // 2
    amplitude = max(1, (upper - lower) // 4)
    path = []
    prior = None
    for along in range(first, last + 1):
        wobble = _noise(0 if vertical else along, along if vertical else 0,
                        seed ^ (0x55bf if vertical else 0x9a61), 12)
        transverse = _clamp(center + round((wobble - .5) * 2 * amplitude),
                            lower + margin, upper - margin)
        if prior is not None:
            for across in range(prior, transverse +
                                (1 if transverse >= prior else -1),
                                1 if transverse >= prior else -1):
                point = (across, along) if vertical else (along, across)
                if not path or point != path[-1]:
                    path.append(point)
        point = (transverse, along) if vertical else (along, transverse)
        if not path or point != path[-1]:
            path.append(point)
        prior = transverse
    return tuple(path)


def _connected(path):
    return bool(path) and all(
        abs(x1 - x0) + abs(y1 - y0) == 1
        for (x0, y0), (x1, y1) in zip(path, path[1:]))


def _eligible(old, point, protected):
    return (point not in protected and not old.get('feature') and
            not old.get('blocked') and not old.get('height', 0) and
            not old.get('hazard', 0) and not old.get('cover', 0) and
            old.get('cost', 1) == 1 and
            old.get('surface', 'grass') not in ('water', 'bridge', 'cobble'))


def _components(width, height, original, planned=None):
    """Traversable components with the same 1-step relief rule for both states."""
    component = {}
    index = 0
    for y in range(height):
        for x in range(width):
            start = x, y
            if start in component:
                continue
            def state(p):
                if planned is not None and p in planned:
                    surface, level, blocked, _ = planned[p]
                    return level, blocked
                old = original.get(p, {})
                return old.get('height', 0), old.get('blocked', False)
            level, blocked = state(start)
            if blocked:
                continue
            component[start] = index
            pending = [start]
            while pending:
                cx, cy = pending.pop()
                level, _ = state((cx, cy))
                for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                    q = (cx+dx, cy+dy)
                    if (q in component or not 0 <= q[0] < width or
                            not 0 <= q[1] < height):
                        continue
                    elevation, barrier = state(q)
                    if not barrier and abs(elevation-level) <= 1:
                        component[q] = index
                        pending.append(q)
            index += 1
    return component


def _preserve_mission_access(mission, original, result):
    """Never split important mission anchors which were connected before."""
    points = [tuple(u['pos']) for u in mission.get('units', ())]
    points.extend(tuple(o['pos']) for o in mission.get('objects', ()))
    points.extend(tuple(p) for p in mission.get('goal', ()))
    points.extend(tuple(p) for zone in mission.get('deployment', ())
                  for p in zone.get('cells', ()))
    if mission.get('relic') is not None:
        points.append(tuple(mission['relic']))
    if len(points) < 2:
        return
    width, height = mission['board']['width'], mission['board']['height']
    before = _components(width, height, original)
    after = _components(width, height, original, result)
    representative = {}
    for point in points:
        group = before.get(point)
        if group is None:
            continue
        if group in representative:
            require(after.get(representative[group]) == after.get(point)
                    and after.get(point) is not None,
                    'Landscape disconnects a mission objective or unit')
        else:
            representative[group] = point


def _landscape(data, mission_id, start, end, *, seed, style, vegetation):
    """Pure planning function; also used to rederive a plan at commit time."""
    require(type(seed) is int and 0 <= seed <= 0x7fffffff,
            'Seed must be a nonnegative 31-bit integer')
    require(style in REGION_STYLES, 'Unknown landscape style')
    require(type(vegetation) is int and 0 <= vegetation <= 3,
            'Vegetation density must be 0..3')
    mission = _mission(data, mission_id)
    cells = cells_in_rectangle(data, mission_id, start, end)
    require(0 < len(cells) <= MAX_CELLS, 'Landscape region exceeds 4096 cells')
    x0, x1 = min(p[0] for p in cells), max(p[0] for p in cells)
    y0, y1 = min(p[1] for p in cells), max(p[1] for p in cells)
    require(x1 - x0 >= 11 and y1 - y0 >= 11,
            'Select a rectangle at least 12 by 12 cells')
    bounds = (x0, y0, x1, y1)
    original = {tuple(t['pos']): t for t in mission['board']['tiles']}
    protected = _reserved_cells(mission)
    # Preserve spawn/deployment footprints and embedded event placement.
    protected.update(
        tuple(point) for zone in mission.get('deployment', ())
        for point in zone.get('cells', ()))
    for trigger in mission.get('triggers', ()):
        for key in ('cell', 'pos'):
            point = trigger.get(key)
            if isinstance(point, (tuple, list)) and len(point) == 2 and all(
                    type(v) is int for v in point):
                protected.add(tuple(point))
        for point in trigger.get('cells', ()):
            if isinstance(point, (tuple, list)) and len(point) == 2 and all(
                    type(v) is int for v in point):
                protected.add(tuple(point))
    editable = {p for p in cells if _eligible(original.get(p, {}), p, protected)}
    vertical_river = (seed & 1) == 0
    river_path = _connected_path(bounds, seed, vertical=vertical_river)
    road_path = _connected_path(bounds, seed ^ 0x193e, vertical=not vertical_river)
    river, road = frozenset(river_path), frozenset(road_path)
    require(_connected(river_path) and _connected(road_path),
            'Procedural route must be cardinally continuous')
    require(bool(river & road), 'Road must intersect the river')
    affected = river | road
    require(affected <= editable,
            'River or road crosses authored content: choose a clear region')
    # A bridge is generated wherever the road passes over the river. Water
    # remains 4-connected via its bridge tiles, with no impassable road cut.
    bridge = river & road
    require(bridge, 'Generated river needs a bridge crossing')
    landmarks = (road_path[len(road_path)//4],
                 road_path[(len(road_path)*3)//4])
    clearings = set()
    for cx, cy in landmarks:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                point = cx + dx, cy + dy
                if abs(dx) + abs(dy) <= 3 and point in editable:
                    clearings.add(point)

    # Mild high ground, deliberately flattened beside the river, road and
    # clearings; player traversal near the main corridor remains predictable.
    corridor = affected | clearings
    buffer = corridor | {
        (x + dx, y + dy) for x, y in affected
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
    }
    result = {}
    for point in cells:
        if point not in editable:
            continue
        x, y = point
        surface = surface_at(x, y, seed=seed, style=style)
        height = 0
        feature = ''
        blocked = False
        if point in river:
            surface, blocked = 'water', True
        elif point in road:
            surface = 'dirt'
        elif point in clearings:
            surface = 'grass'
        else:
            nearby_water = any(
                (x+dx, y+dy) in river or
                original.get((x+dx, y+dy), {}).get('surface') == 'water'
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            # Banks mix native grass, earthy pigment and sparse sand. Their
            # varied watercolor transitions come from the existing atlas.
            if nearby_water and _hash(x, y, seed ^ 0x8e21) % 4 != 0:
                surface = ('sand' if style in ('aride', 'vallon')
                           else 'dirt')
            if point not in buffer:
                slope = (.78 * _noise(x, y, seed ^ 0x7451, 15) +
                         .22 * _noise(x, y, seed ^ 0x34a7, 7))
                height = 1 if slope > .66 else 0
            if vegetation:
                feature = biome_feature_at(
                    x, y, seed=seed, style=style, surface=surface,
                    vegetation=vegetation, near_water=nearby_water)
        if point in bridge:
            surface, blocked, height, feature = 'bridge', False, 0, ''
        result[point] = (surface, height, blocked, feature)
    # A route crossing must be walkable, and the former water course must
    # still be physically continuous via the bridge sprites.
    require(all(result[point][0] in ('dirt', 'bridge') and
                not result[point][2] and result[point][1] == 0
                for point in road), 'Generated route must stay walkable')
    require(all(result[point][0] in ('water', 'bridge')
                for point in river), 'River must remain continuous')
    _preserve_mission_access(mission, original, result)
    changes = []
    for x, y in cells:  # row-major
        point = x, y
        if point not in result:
            continue
        values = result[point]
        current = original.get(point, {})
        if values != (current.get('surface', 'grass'),
                      current.get('height', 0),
                      current.get('blocked', False),
                      current.get('feature', '')):
            changes.append((x, y, *values))
    return NaturalMapPlan(
        mission_id, (x0, y0), (x1, y1), seed, style, vegetation,
        _fingerprint(data), tuple(changes),
        tuple(river_path), tuple(road_path),
        tuple(sorted(clearings, key=lambda p: (p[1], p[0]))))


def plan_natural_map(data, mission_id, start, end, *, seed=1,
                     style='bocage', vegetation=2):
    """Inspect the plan without mutating the source, history or RNG."""
    return _landscape(data, mission_id, start, end,
                      seed=seed, style=style, vegetation=vegetation)


def apply_natural_map(data, plan):
    """Reconstruct and verify the *entire* plan, then validate one Content edit."""
    require(isinstance(plan, NaturalMapPlan), 'Expected natural map plan')
    require(_fingerprint(data) == plan.source_sha256,
            'Natural map preview is stale; preview again')
    expected = _landscape(
        data, plan.mission_id, plan.start, plan.end, seed=plan.seed,
        style=plan.style, vegetation=plan.vegetation)
    require(expected == plan, 'Natural map preview no longer matches its source')
    if not plan.changes:
        return data
    updated = deepcopy(data)
    mission = _mission(updated, plan.mission_id)
    tiles = {tuple(tile['pos']): tile for tile in mission['board']['tiles']}
    for x, y, surface, height, blocked, feature in plan.changes:
        old = tiles.get((x, y), {'pos': [x, y]})
        tiles[(x, y)] = {
            **old, 'surface': surface, 'height': height,
            'blocked': blocked, 'feature': feature,
        }
    mission['board']['tiles'] = list(tiles.values())
    return Content.from_dict(updated).to_dict()
