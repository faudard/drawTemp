"""Original, independently illustrated interactive-object PNG sprites.

Seven transparent 48x64 frames on one horizontal atlas. Presentation only:
objects continue to use the existing Content and interaction contracts.
"""
from pathlib import Path
from .tk_images import crop_scaled

OBJECT_SPRITE_NAMES = (
    'door', 'switch', 'chest', 'ram', 'catapult', 'passage', 'defense')
OBJECT_FRAME = (48, 64)
OBJECT_BASE_CELL = 54
DEFAULT_OBJECT_ATLAS = (Path(__file__).parent / 'content' / 'art' /
                        'iso' / 'interactive_objects.png')


class IsoObjectAtlas:
    def __init__(self, canvas, path=DEFAULT_OBJECT_ATLAS):
        self.canvas = canvas
        self.path = Path(path)
        self._source = None
        self._cache = {}
        self._unavailable = False

    def sprite(self, kind, cell_size):
        if (kind not in OBJECT_SPRITE_NAMES or type(cell_size) is not int
                or cell_size < 1 or self._unavailable):
            return None
        key = kind, cell_size
        if key in self._cache:
            return self._cache[key]
        # Headless renderer tests use a fake Canvas without a Tk interpreter.
        # Keep vector fallback instead of creating a PhotoImage on that mock.
        if not callable(getattr(getattr(self.canvas, 'tk', None), 'call', None)):
            return None
        try:
            import tkinter as tk
        except ImportError:
            self._unavailable = True
            return None
        try:
            if self._source is None:
                source = tk.PhotoImage(master=self.canvas, file=str(self.path))
                if (source.width(), source.height()) != (
                        OBJECT_FRAME[0] * len(OBJECT_SPRITE_NAMES),
                        OBJECT_FRAME[1]):
                    raise ValueError('Invalid interactive object atlas dimensions')
                self._source = source
            width, height = OBJECT_FRAME
            x = OBJECT_SPRITE_NAMES.index(kind) * width
            photo = crop_scaled(
                self._source, (x, 0, width, height),
                (max(1, round(width * cell_size / OBJECT_BASE_CELL)),
                 max(1, round(height * cell_size / OBJECT_BASE_CELL))),
                master=self.canvas)
            self._cache[key] = photo
            return photo
        except (OSError, ValueError, RuntimeError, tk.TclError):
            self._unavailable = True
            return None

    def clear_cache(self):
        self._cache.clear()
        self._source = None
        self._unavailable = False
