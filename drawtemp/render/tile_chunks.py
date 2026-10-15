"""R3.B visible-chunk index shared by every Qt viewport client.

This is a CPU-side spatial index. It does not pretend to be GPU batching.
It stores only presentation data, never canonical tactical objects.
"""
from math import floor
from .iso_scene import IsoProjection


class TileChunkIndex:
    def __init__(self, scene, *, chunk_size=16):
        if type(chunk_size) is not int or chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer")
        self.chunk_size = chunk_size
        self.width, self.height = scene["width"], scene["height"]
        self.chunks = {}
        self.tiles = {}
        self.elevations = {}
        self.min_height = 0
        self.max_height = 0
        self.update(scene)

    def update(self, scene):
        """Replace only changed tile records in their owning chunks.

        Returns coordinates of added, removed or modified tiles. Scene inputs
        are detached R3 presentation dicts; the index copies tile dictionaries.
        """
        if (scene["width"], scene["height"]) != (self.width, self.height):
            raise ValueError("Map dimensions changed; create a new chunk index")
        current = {(t["x"], t["y"]): dict(t) for t in scene["tiles"]}
        if any(not (0 <= x < self.width and 0 <= y < self.height)
               for x, y in current):
            raise ValueError("Out-of-bounds terrain tile")
        if len(current) != len(scene["tiles"]):
            raise ValueError("Duplicate terrain tile")
        dirty = {cell for cell in self.tiles.keys() | current.keys()
                 if self.tiles.get(cell) != current.get(cell)}
        for cell in dirty:
            cx, cy = cell[0] // self.chunk_size, cell[1] // self.chunk_size
            chunk = self.chunks.setdefault((cx, cy), {})
            if cell in current:
                chunk[cell] = current[cell]
                self.tiles[cell] = current[cell]
            else:
                chunk.pop(cell, None)
                self.tiles.pop(cell, None)
            if not chunk:
                self.chunks.pop((cx, cy), None)
        heights = [t["height"] for t in self.tiles.values()]
        self.min_height = min([0, *heights])
        self.max_height = max([0, *heights])
        self.elevations = {cell: tile["height"] for cell, tile in self.tiles.items()}
        return dirty

    def visible_bounds(self, camera, projection=IsoProjection(), *, margin=2):
        """Conservative inverse AABB over all elevation planes.

        Includes camera zoom, both positive/negative height, and pixel margin.
        It may return extra cells, but never rejects a visible tile diamond.
        """
        padding = max(projection.width, projection.height) * margin
        corners = [camera.world(x, y)
                   for x in (-padding, camera.width + padding)
                   for y in (-padding, camera.height + padding)]
        coords = [projection.unproject(x, y, elevation)
                  for x, y in corners
                  for elevation in (self.min_height, self.max_height)]
        return (max(0, floor(min(x for x, _ in coords)) - margin - 1),
                min(self.width - 1, floor(max(x for x, _ in coords)) + margin + 1),
                max(0, floor(min(y for _, y in coords)) - margin - 1),
                min(self.height - 1, floor(max(y for _, y in coords)) + margin + 1))

    def visible_tiles(self, camera, projection=IsoProjection()):
        lo_x, hi_x, lo_y, hi_y = self.visible_bounds(camera, projection)
        if hi_x < lo_x or hi_y < lo_y:
            return ()
        size = self.chunk_size
        rows = []
        for cy in range(lo_y // size, hi_y // size + 1):
            for cx in range(lo_x // size, hi_x // size + 1):
                chunk = self.chunks.get((cx, cy), {})
                rows.extend(tile for (x, y), tile in chunk.items()
                            if lo_x <= x <= hi_x and lo_y <= y <= hi_y)
        return rows
