"""Original chibi actors for the shared isometric Editor/Player view.

Visual-only PNGs, with graceful vector fallback. The tactical Content contract,
RNG, save/replay and AI never depend on these presentation sprites.
"""
from pathlib import Path

from .tk_images import crop_scaled

ACTOR_STYLES = ('hero', 'guard', 'archer', 'jeanne')
ACTOR_DIRECTIONS = ('south', 'north', 'east', 'west')
ACTOR_FRAMES = 2
ACTOR_FRAME_SIZE = (64, 64)
ACTOR_SOURCE_CELL_SIZE = 54
DEFAULT_ACTOR_ATLAS = (Path(__file__).parent / 'content' / 'art'
                       / 'iso' / 'chibi_actors.png')
DEFAULT_JEANNE_ATLAS = (Path(__file__).parent / 'content' / 'art'
                       / 'jeanne' / 'jeanne_atlas.png')


def actor_style(actor):
    """Select an illustration without persisting any new gameplay field."""
    if (str(getattr(actor, 'id', '')).casefold() == 'jeanne'
            or str(getattr(actor, 'name', '')).casefold() == 'jeanne'):
        return 'jeanne'
    archetype = getattr(actor, 'archetype', '')
    weapon = getattr(actor, 'weapon', '')
    if (archetype in ('archer', 'ranger', 'bowman', 'crossbowman')
            or weapon in ('bow', 'crossbow', 'longbow')):
        return 'archer'
    team = getattr(actor, 'team', None)
    return 'hero' if team == 'player' else 'guard' if team == 'enemy' else 'archer'


def actor_direction(actor, pose=None):
    """A MotionDirector pose takes precedence over the unit's stored facing."""
    direction = getattr(pose, 'direction', None)
    if direction in ACTOR_DIRECTIONS:
        return direction
    facing = getattr(actor, 'facing', (0, 1))
    if not isinstance(facing, (tuple, list)) or len(facing) != 2:
        return 'south'
    x, y = facing
    if type(x) not in (int, float) or type(y) not in (int, float):
        return 'south'
    if abs(x) > abs(y):
        return 'east' if x > 0 else 'west'
    return 'south' if y >= 0 else 'north'


def actor_frame(pose=None):
    """Two safe frames: pose changes are cosmetic, not simulation clocks."""
    return int(getattr(pose, 'action', '') == 'move')


class IsoActorAtlas:
    """Cached nearest-neighbour Tk actor PNG; missing art never breaks play."""
    def __init__(self, canvas, path=DEFAULT_ACTOR_ATLAS,
                 jeanne_path=DEFAULT_JEANNE_ATLAS):
        self.canvas = canvas
        self.path = Path(path)
        self.jeanne_path = Path(jeanne_path)
        self._source = None
        self._jeanne_source = None
        self._cache = {}
        self._unavailable = False
        self._jeanne_unavailable = False

    def sprite(self, style, direction, frame, cell_size):
        if (style not in ACTOR_STYLES
                or direction not in ACTOR_DIRECTIONS
                or type(frame) is not int or frame not in range(ACTOR_FRAMES)
                or type(cell_size) is not int or cell_size < 1):
            return None
        key = (style, direction, frame, cell_size)
        if key in self._cache:
            return self._cache[key]
        try:
            import tkinter as tk
        except ImportError:
            self._unavailable = True
            return None
        width, height = ACTOR_FRAME_SIZE
        size = (max(1, round(width * cell_size / ACTOR_SOURCE_CELL_SIZE)),
                max(1, round(height * cell_size / ACTOR_SOURCE_CELL_SIZE)))
        if style == 'jeanne' and not self._jeanne_unavailable:
            try:
                if self._jeanne_source is None:
                    source = tk.PhotoImage(file=str(self.jeanne_path),
                                           master=self.canvas)
                    if (source.width(), source.height()) != (256, 512):
                        raise ValueError('Invalid Jeanne atlas dimensions')
                    self._jeanne_source = source
                # Existing approved Jeanne atlas: four direction columns and
                # idle_0 / move_0 on rows 0 / 2, respectively.
                x = ACTOR_DIRECTIONS.index(direction) * width
                y = (2 if frame else 0) * height
                photo = crop_scaled(self._jeanne_source, (x, y, width, height),
                                    size, master=self.canvas)
                self._cache[key] = photo
                return photo
            except (AttributeError, OSError, RuntimeError, TypeError,
                    ValueError, tk.TclError):
                self._jeanne_unavailable = True
                # Missing Jeanne art must not prevent generic team rendering.
        if self._unavailable:
            return None
        try:
            if self._source is None:
                source = tk.PhotoImage(file=str(self.path), master=self.canvas)
                if ((source.width(), source.height())
                        != (width * len(ACTOR_DIRECTIONS) * ACTOR_FRAMES,
                            height * (len(ACTOR_STYLES) - 1))):
                    raise ValueError('Invalid chibi actor atlas dimensions')
                self._source = source
            fallback = 'hero' if style == 'jeanne' else style
            x = (ACTOR_DIRECTIONS.index(direction) * ACTOR_FRAMES + frame) * width
            y = ACTOR_STYLES.index(fallback) * height
            photo = crop_scaled(self._source, (x, y, width, height), size,
                                master=self.canvas)
            self._cache[key] = photo
            return photo
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError,
                tk.TclError):
            self._unavailable = True
            return None

    def clear_cache(self):
        self._cache.clear()
        self._source = None
        self._jeanne_source = None
        self._unavailable = False
        self._jeanne_unavailable = False
