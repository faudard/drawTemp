"""R3.B visible-chunk index shared by every Qt viewport client.

This is a CPU-side spatial index. It does not pretend to be GPU batching.
It stores only presentation data, never canonical tactical objects.
"""
from collections import OrderedDict
from math import floor
from .iso_scene import IsoProjection


# The cache owns only (x, y) coordinates. It never owns another copy of tile
# dictionaries, and misses fall back to the same existing chunk traversal.
DEFAULT_VISIBILITY_CACHE_BYTES = 256 * 1024
DEFAULT_VISIBILITY_CACHE_ENTRIES = 16
ESTIMATED_CELL_BYTES = 128  # conservative bound incl. tuple/list overhead


class BoundedVisibilityCache:
    """LRU for viewport result coordinates, independent from game state.

    The byte count is an estimated upper bound for stored coordinate entries,
    not a process RSS measurement. Large views render uncached rather than
    retaining an unbounded list. Updates clear the entire cache before reuse.
    """

    def __init__(self, budget=DEFAULT_VISIBILITY_CACHE_BYTES,
                 max_entries=DEFAULT_VISIBILITY_CACHE_ENTRIES):
        if type(budget) is not int or budget <= 0:
            raise ValueError("Visibility budget must be a positive integer")
        if type(max_entries) is not int or not 1 <= max_entries <= 64:
            raise ValueError("Visibility entries must be an integer in 1..64")
        self.budget = budget
        self.max_entries = max_entries
        self._entries = OrderedDict()
        self.bytes_used = 0
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.bypasses = 0

    def get(self, bounds):
        cells = self._entries.get(bounds)
        if cells is None:
            self.misses += 1
        else:
            self.hits += 1
            self._entries.move_to_end(bounds)
        return cells

    def put(self, bounds, cells):
        size = len(cells) * ESTIMATED_CELL_BYTES + 128
        if size > self.budget:
            self.bypasses += 1
            return False
        old = self._entries.pop(bounds, None)
        if old is not None:
            self.bytes_used -= len(old) * ESTIMATED_CELL_BYTES + 128
        while (self._entries and
               (len(self._entries) >= self.max_entries or
                self.bytes_used + size > self.budget)):
            _, removed = self._entries.popitem(last=False)
            self.bytes_used -= len(removed) * ESTIMATED_CELL_BYTES + 128
            self.evictions += 1
        self._entries[bounds] = tuple(cells)
        self.bytes_used += size
        return True

    def clear(self):
        self._entries.clear()
        self.bytes_used = 0

    def stats(self):
        return {"entries": len(self._entries), "bytes": self.bytes_used,
                "budget": self.budget, "hits": self.hits,
                "misses": self.misses, "evictions": self.evictions,
                "bypasses": self.bypasses}



class TileChunkIndex:
    def __init__(self, scene, *, chunk_size=16,
                 visibility_budget=DEFAULT_VISIBILITY_CACHE_BYTES,
                 visibility_entries=DEFAULT_VISIBILITY_CACHE_ENTRIES):
        self.visibility_cache = BoundedVisibilityCache(
            budget=visibility_budget, max_entries=visibility_entries)
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
        # During camera-only refresh the source is unchanged: retain the
        # elevation lookup and chunk allocation instead of rebuilding them.
        if not dirty:
            return dirty
        # A changed elevation can move any tile into/out of a projected AABB.
        # Clear before changing the index to avoid stale or partial reads.
        self.visibility_cache.clear()
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
        bounds = self.visible_bounds(camera, projection)
        lo_x, hi_x, lo_y, hi_y = bounds
        if hi_x < lo_x or hi_y < lo_y:
            return ()
        cells = self.visibility_cache.get(bounds)
        if cells is None:
            size = self.chunk_size
            coords = []
            # Retain original R3 iteration order for stable depth/render data.
            for cy in range(lo_y // size, hi_y // size + 1):
                for cx in range(lo_x // size, hi_x // size + 1):
                    chunk = self.chunks.get((cx, cy), {})
                    coords.extend((x, y) for x, y in chunk
                                  if lo_x <= x <= hi_x and lo_y <= y <= hi_y)
            cells = tuple(coords)
            self.visibility_cache.put(bounds, cells)
        # Do not expose cached mutable tile dicts. Look up the current index
        # records every time and return a fresh list as pre-R52 callers expect.
        return [self.tiles[cell] for cell in cells]

    @property
    def visibility_stats(self):
        return self.visibility_cache.stats()
