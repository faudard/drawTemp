"""Packaged medieval prop atlas for the isometric map editor.

Sprites are presentation-only and anchored at the tile centre. The module
does not import Tk until a sprite is requested, keeping headless builds safe.
"""
from pathlib import Path

from .tk_images import crop_scaled

PROP_NAMES = ('tree', 'bush', 'boulder', 'ruin', 'crate', 'lantern',
              'stairs', 'stone_wall', 'arch', 'fence', 'reeds', 'pillar')
PROP_FRAME_SIZE = (96, 128)
DEFAULT_PROP_ATLAS = Path(__file__).parent / 'content' / 'art' / 'iso' / 'props.png'


class IsoPropAtlas:
    """Cached transparent sprites. Returns None if PNG/Tk is unavailable."""
    def __init__(self, canvas, path=DEFAULT_PROP_ATLAS):
        self.canvas = canvas
        self.path = Path(path)
        self._source = None
        self._cache = {}
        self._unavailable = False

    def sprite(self, name, cell_size):
        if (self._unavailable or name not in PROP_NAMES or
                type(cell_size) is not int or cell_size < 1):
            return None
        key = (name, cell_size)
        if key in self._cache:
            return self._cache[key]
        try:
            import tkinter as tk
        except ImportError:
            self._unavailable = True
            return None
        try:
            width, height = PROP_FRAME_SIZE
            if self._source is None:
                source = tk.PhotoImage(file=str(self.path), master=self.canvas)
                if (source.width() != width * len(PROP_NAMES) or
                        source.height() != height):
                    raise ValueError('Unexpected prop atlas dimensions')
                self._source = source
            tw = max(1, round(width * cell_size / 54))
            th = max(1, round(height * cell_size / 54))
            x = PROP_NAMES.index(name) * width
            result = crop_scaled(self._source, (x, 0, width, height), (tw, th),
                                 master=self.canvas)
            self._cache[key] = result
            return result
        except (OSError, RuntimeError, ValueError, tk.TclError):
            self._unavailable = True
            return None

    def clear_cache(self):
        self._cache.clear()
