"""Conservative 3.7.32E tile invalidation for a validated editor scene.

This module is Tk-free. Return None when a partial Canvas repaint cannot
be proven equivalent to the full isometric renderer. Dirty paints do not
alter tactical rules or the authored Content serialization.
"""
from dataclasses import replace

from .iso_architecture import architecture_instances


def affected_terrain_cells(before, after, *, geometry, max_changed=16,
                           max_affected=144):
    """Return affected (x,y) cells, empty for a true no-op, None for fallback.

    Static actors, objects, props and buildings are supported when metadata
    and architecture instances remain identical. Elevation changes fall back
    because they may affect global isometric geometry.
    """
    if before is None or after is None or geometry is None:
        return None
    old_board, board = before.board, after.board
    if (old_board.width, old_board.height) != (board.width, board.height):
        return None
    if geometry.board is not old_board:
        return None
    # Only validated board-only mutations qualify. Static units, objects,
    # roofs, facades and props may remain as long as scene identity is stable.
    if replace(before, board=board) != after:
        return None
    # A terrain change can create or break a legacy structure stamp.
    # Revalidate using the same architecture detector as the full painter.
    if tuple(architecture_instances(board, after.structures)) != tuple(
            getattr(geometry, 'architecture_instances', ())):
        return None
    changed = set()
    for cell in old_board.tiles.keys() | board.tiles.keys():
        old, new = old_board.tile(cell), board.tile(cell)
        if old == new:
            continue
        if old.height != new.height:
            return None
        changed.add(cell)
        if len(changed) > max_changed:
            return None
    if not changed:
        return frozenset()
    # Chebyshev radius 1 conservatively covers shoreline masks, bridge
    # alignment and visible east/south walls (including diagonals).
    affected = set()
    for x, y in changed:
        affected.update(
            (x+dx, y+dy)
            for dy in (-1, 0, 1) for dx in (-1, 0, 1)
            if board.contains((x+dx, y+dy))
        )
        if len(affected) > max_affected:
            return None
    # Static actors, objects and props are owned by their isometric cell.
    # Multi-cell actors need a dedicated footprint dependency planner.
    if any(getattr(unit, 'footprint', (1, 1)) != (1, 1)
           for unit in after.units):
        return None
    return frozenset(affected)
