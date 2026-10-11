"""Deterministic isometric river and bridge connectors.

The tactical board is the authority; this module has no graphics or Tk imports.
Neighbour masks describe *visual* transitions only. Bridges count as part of
the channel so they never introduce artificial banks.
"""
N, E, S, W = 1, 2, 4, 8
DIRECTIONS = ((0, -1, N), (1, 0, E), (0, 1, S), (-1, 0, W))


def channel(board, cell):
    return (board.contains(cell) and
            board.tile(cell).surface in ('water', 'bridge'))


def shoreline_mask(board, cell):
    """Boundary edges against terrain, in NESW bit order (not board edges)."""
    if not board.contains(cell) or board.tile(cell).surface != 'water':
        return 0
    x, y = cell
    return sum(bit for dx, dy, bit in DIRECTIONS
               if board.contains((x + dx, y + dy))
               and not channel(board, (x + dx, y + dy)))


def waterfall_mask(board, cell):
    """Exposed water-to-water descending edges; only visible +x/+y faces."""
    if not board.contains(cell) or board.tile(cell).surface != 'water':
        return 0
    x, y = cell
    height = board.tile(cell).height
    return sum(bit for dx, dy, bit in DIRECTIONS
               if bit in (E, S) and channel(board, (x + dx, y + dy))
               and board.tile((x + dx, y + dy)).surface == 'water'
               and board.tile((x + dx, y + dy)).height < height)


def bridge_axis(board, cell):
    """Return bridge walk axis ('x' or 'y') from adjacent channel geometry.

    A river travelling along y needs a bridge across x. Adjacent bridge tiles
    are counted as part of the channel, and an isolated bridge defaults to x.
    """
    if not board.contains(cell) or board.tile(cell).surface != 'bridge':
        return None
    x, y = cell
    flow_y = int(channel(board, (x, y-1))) + int(channel(board, (x, y+1)))
    flow_x = int(channel(board, (x-1, y))) + int(channel(board, (x+1, y)))
    return 'x' if flow_y >= flow_x else 'y'


def transition_segments(corners, mask):
    """Visual segments on the north/east/south/west faces of a diamond."""
    north, east, south, west = corners
    edges = ((N, (west, north)), (E, (east, south)),
             (S, (south, west)), (W, (north, east)))
    return tuple(segment for bit, segment in edges if mask & bit)


def bridge_rails(corners, axis):
    """Two outer rail segments for a bridge aligned along board x or y."""
    north, east, south, west = corners
    if axis == 'x':
        return (west, north), (south, east)
    return (north, east), (west, south)
