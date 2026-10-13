"""Map Builder 4.0A — headless, deterministic smart brush footprints.

Uses the existing tactical board, sparse tiles, and validated Document.paint_many.
The isometric renderer already derives shoreline and bridge connections from
neighbouring terrain; no connector tiles or extra serialized fields are needed.
"""
from .iso_map import _line_cells
from .map_authoring import _cell, _mission, selected_cells
from .model import require


def smart_brush_cells(data, mission_id, anchors, *, radius=0, shape='diamond'):
    """Expand a connected pointer stroke to a clipped, unique brush footprint.

    The cursor anchors must belong to the map; the footprint may touch its edge.
    Each segment uses the *existing* Bresenham helper, so fast mouse movement
    cannot leave gaps. Order is canonical for reproducible output.
    """
    require(type(radius) is int and 0 <= radius <= 3,
            'Brush radius must be an integer between 0 and 3')
    require(shape in ('diamond', 'square'), 'Unknown brush shape')
    require(isinstance(anchors, (list, tuple)) and bool(anchors),
            'A brush stroke needs at least one anchor')
    mission = _mission(data, mission_id)
    centers = [_cell(mission, p) for p in anchors]
    width, height = mission['board']['width'], mission['board']['height']
    cells = set()
    for index, end in enumerate(centers):
        starts = (end,) if index == 0 else _line_cells(centers[index - 1], end)
        for x, y in starts:
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if shape == 'diamond' and abs(dx) + abs(dy) > radius:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        cells.add((nx, ny))
    return tuple(sorted(cells, key=lambda c: (c[1], c[0])))


def surface_region(data, mission_id, start, *, allowed_cells=None):
    """Four-connected same-surface area, optionally confined to selected cells.

    None means no restriction. An empty selection is rejected, rather than
    accidentally filling the entire map. Sparse tiles default to grass.
    """
    mission = _mission(data, mission_id)
    seed = _cell(mission, start)
    allowed = None
    if allowed_cells is not None:
        allowed = set(selected_cells(data, mission_id, allowed_cells))
        require(seed in allowed, 'Start cell must belong to the selection')
    width, height = mission['board']['width'], mission['board']['height']
    tiles = {tuple(tile['pos']): tile for tile in mission['board']['tiles']}
    old_surface = tiles.get(seed, {}).get('surface', 'grass')
    result, visited, pending = set(), set(), [seed]
    while pending:
        cell = pending.pop()
        x, y = cell
        if cell in visited or not (0 <= x < width and 0 <= y < height):
            continue
        visited.add(cell)
        if (allowed is not None and cell not in allowed or
                tiles.get(cell, {}).get('surface', 'grass') != old_surface):
            continue
        result.add(cell)
        pending.extend(((x-1, y), (x+1, y), (x, y-1), (x, y+1)))
    return tuple(sorted(result, key=lambda c: (c[1], c[0])))
