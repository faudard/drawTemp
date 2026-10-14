"""Conservative 3.7.32E tile invalidation for a validated editor scene.

This module is Tk-free. Return None when a partial Canvas repaint cannot
be proven equivalent to the full isometric renderer. Dirty paints do not
alter tactical rules or the authored Content serialization.
"""
from dataclasses import replace


def affected_terrain_cells(before, after, *, geometry, max_changed=16,
                           max_affected=144):
    """Return affected (x,y) cells, empty for a true no-op, None for fallback.

    Only a simple, static map with unchanged elevation and no depth-ordering
    dependencies can use this initial fast path. Water shoreline, bridge
    orientation and visible side faces depend on surrounding tiles.
    """
    if before is None or after is None or geometry is None:
        return None
    old_board, board = before.board, after.board
    if (old_board.width, old_board.height) != (board.width, board.height):
        return None
    if geometry.board is not old_board:
        return None
    # This check includes all authored metadata other than Board. Forbid any
    # actor/object/structure/upper deck or decor until an occlusion-aware
    # tile/actor dependency graph has a full-scene parity gate.
    if replace(before, board=board) != after:
        return None
    if (after.units or after.objects or after.structures or
            after.interior_floors or after.unit_levels or after.level_links or
            any(t.feature for t in board.tiles.values()) or
            any(t.feature for t in old_board.tiles.values()) or
            getattr(geometry, 'architecture_instances', ())):
        return None
    changed = set()
    for cell in old_board.tiles.keys() | board.tiles.keys():
        old, new = old_board.tile(cell), board.tile(cell)
        if old == new:
            continue
        if old.height != new.height or old.feature != new.feature:
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
    return frozenset(affected)
