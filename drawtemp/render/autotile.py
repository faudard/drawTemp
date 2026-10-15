"""Shared R3/R5/R12 AutoBlend metadata; presentation only, no terrain mutations."""
from __future__ import annotations

from sporebound.terrain_autoblend import (
    BlendEdge, blend_edges, blend_polygon, LAND_COLORS,
)
from sporebound.iso_connections import DIRECTIONS, shoreline_mask, bridge_axis


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
        edges = list(blend_edges(board, (tile["x"], tile["y"])))
        # Water/bridge use the canonical channel and shoreline masks, so a
        # painted river receives banks without inserting connector tiles.
        shore = shoreline_mask(board, (tile["x"], tile["y"]))
        edges.extend(BlendEdge(bit, "shoreline", 0)
                     for _, _, bit in DIRECTIONS if shore & bit)
        for edge in edges:
            poly = blend_polygon(corners, edge)
            # Match the whole irregular legacy polygon, not a flat quad.
            points = [[poly[i], poly[i+1]] for i in range(0, len(poly), 2)]
            joins.append({
                "bit": edge.bit, "incoming": edge.incoming,
                "color": "#9bc6ce" if edge.incoming == "shoreline"
                         else LAND_COLORS[edge.incoming], "points": points,
            })
        tile["blends"] = joins
        tile["bridgeAxis"] = bridge_axis(board, (tile["x"], tile["y"]))
        result.append(tile)
    return result
