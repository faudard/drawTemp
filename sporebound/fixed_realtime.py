"""R25.C — Deterministic subcell locomotion for routed exploration scenes.

Pure headless grid collisions. Rendering interpolates snapshots, never advances
the simulation. Continuous free movement here means integer subcell steps,
not a claim of complete action combat, controller input or physics.
"""
from .model import require

UNITS_PER_TILE = 256
AXIS_STEP = 32
DIAGONAL_STEP = 23


class FreeMovement:
    """Move a point-shaped hero with integer fixed-step obstacle collision."""

    def __init__(self, stage):
        require(type(stage) is dict and
                all(key in stage for key in ("width", "height", "blocked")),
                "Malformed free movement stage")
        self.width, self.height = stage["width"], stage["height"]
        require(type(self.width) is int and type(self.height) is int
                and 3 <= self.width <= 32 and 3 <= self.height <= 32,
                "Invalid free movement stage dimensions")
        blocked = stage["blocked"]
        require(type(blocked) is list and len(blocked) <= self.width * self.height,
                "Invalid free movement obstacles")
        cells = set()
        for cell in blocked:
            require(type(cell) is list and len(cell) == 2
                    and all(type(p) is int for p in cell)
                    and 0 <= cell[0] < self.width
                    and 0 <= cell[1] < self.height,
                    "Invalid free movement obstacle")
            require(tuple(cell) not in cells, "Duplicate obstacle")
            cells.add(tuple(cell))
        self.blocked = frozenset(cells)

    def center(self, cell):
        require(type(cell) is list and len(cell) == 2
                and all(type(p) is int for p in cell)
                and 0 <= cell[0] < self.width
                and 0 <= cell[1] < self.height
                and tuple(cell) not in self.blocked,
                "Invalid initial free movement cell")
        return [cell[0] * UNITS_PER_TILE + UNITS_PER_TILE // 2,
                cell[1] * UNITS_PER_TILE + UNITS_PER_TILE // 2]

    def cell(self, position):
        require(type(position) is list and len(position) == 2
                and all(type(p) is int for p in position)
                and self._clear(position[0], position[1]),
                "Invalid free movement position")
        return [position[0] // UNITS_PER_TILE,
                position[1] // UNITS_PER_TILE]

    def _clear(self, x, y):
        return (0 <= x < self.width * UNITS_PER_TILE
                and 0 <= y < self.height * UNITS_PER_TILE
                and (x // UNITS_PER_TILE, y // UNITS_PER_TILE) not in self.blocked)

    def advance(self, position, dx, dy):
        """Advance one tick with wall sliding and no diagonal corner cutting."""
        self.cell(position)
        require(type(dx) is int and type(dy) is int
                and dx in (-1, 0, 1) and dy in (-1, 0, 1),
                "Free movement requires signed unit axes")
        if not dx and not dy:
            return list(position)
        distance = DIAGONAL_STEP if dx and dy else AXIS_STEP
        x, y = position
        nx, ny = x + dx * distance, y + dy * distance
        can_x = self._clear(nx, y)
        can_y = self._clear(x, ny)
        if dx and dy:
            if can_x and can_y and self._clear(nx, ny):
                return [nx, ny]
            # Sliding is axis-local: never teleport through a blocked corner.
            if can_x:
                return [nx, y]
            if can_y:
                return [x, ny]
            return [x, y]
        return [nx if can_x else x, ny if can_y else y]


__all__ = ["FreeMovement", "UNITS_PER_TILE", "AXIS_STEP", "DIAGONAL_STEP"]
