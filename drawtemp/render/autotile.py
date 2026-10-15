"""Shared R3/R5/R12 AutoBlend metadata; presentation only, no terrain mutations."""
from __future__ import annotations

from sporebound.terrain_autoblend import blend_edges, blend_polygon, LAND_COLORS


class _Tile:
    __slots__ = ("surface", "height")

    def __init__(self, surface="grass", height=0):
        self.surface, self.height = surface, height


class _Board:
    def __init__(self, width, height, tiles):
        self.width, self.height = width, height
        self.cells = {(t["x"], t["y"]): _Tile(t["surface"], t["height"])
                      for t in tiles}
        self.default = _Tile()

    def contains(self, cell):
        return 0 <= cell[0] < self.width and 0 <= cell[1] < self.height

    def tile(self, cell):
        return self.cells.get(cell, self.default)


def autotile_tiles(tiles, width, height):
    """Decorate a detached R3 scene with the existing neighbour-aware joins.

    Edge pixels still use canonical map materials; the irregular inner
    polygon is a visual overlay. Water/bridge keep their existing shoreline
    policy and elevations never bleed into another floor.
    """
    board = _Board(width, height, tiles)
    corners = ((48, 0), (96, 24), (48, 48), (0, 24))
    result = []
    for original in tiles:
        tile = dict(original)
        joins = []
        for edge in blend_edges(board, (tile["x"], tile["y"])):
            poly = blend_polygon(corners, edge)
            # First, last, then two inner points. Four vertices make an
            # inspectable GPU ShapePath strip with no CPU raster copies.
            points = [[poly[i], poly[i+1]] for i in (0, 2, 4, len(poly)-2)]
            joins.append({
                "bit": edge.bit, "incoming": edge.incoming,
                "color": LAND_COLORS[edge.incoming], "points": points,
            })
        tile["blends"] = joins
        result.append(tile)
    return result
