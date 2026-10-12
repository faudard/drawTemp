"""Original pixel-art architecture PNG atlas for the isometric map editor.

Frame order: Maison/0, Maison/1, Tour/0, Tour/1, Ruines/0, Ruines/1.
Sprites are decorative overlays inferred from existing authored terrain.
Never import tkinter (or Pillow) until a visual sprite is requested.
"""
from pathlib import Path

from .tk_images import crop_scaled

BUILDING_FRAMES = (('Maison', 0), ('Maison', 1),
                   ('Tour', 0), ('Tour', 1),
                   ('Ruines', 0), ('Ruines', 1))
BUILDING_FRAME_SIZE = (350, 220)
# The assets were authored at an isometric half-width of 36 source pixels.
BUILDING_SOURCE_CELL_SIZE = 36
BUILDING_ROOF_NORTH = (175, 22)
DEFAULT_BUILDING_ATLAS = (Path(__file__).parent / 'content' / 'art'
                          / 'iso' / 'buildings.png')


def building_sprite_top_left(geo, building):
    """Anchor a frame's roof-north pixel to the rendered building roof."""
    from .iso_architecture import architecture_outline
    north = architecture_outline(geo, building)[0][0]
    scale = geo.cell_size / BUILDING_SOURCE_CELL_SIZE
    return (north[0]-BUILDING_ROOF_NORTH[0]*scale,
            north[1]-BUILDING_ROOF_NORTH[1]*scale)


class IsoBuildingAtlas:
    """Cache Tk PhotoImage crops at zoom; preserve a vector-only fallback."""
    def __init__(self, canvas, path=DEFAULT_BUILDING_ATLAS):
        self.canvas = canvas
        self.path = Path(path)
        self._source = None
        self._cache = {}
        self._unavailable = False

    def sprite(self, name, turns, cell_size):
        if (self._unavailable or type(turns) is not int
                or type(cell_size) is not int or cell_size < 1
                or (name, turns % 2) not in BUILDING_FRAMES):
            return None
        key = (name, turns % 2, cell_size)
        if key in self._cache:
            return self._cache[key]
        try:
            import tkinter as tk
        except ImportError:
            self._unavailable = True
            return None
        try:
            fw, fh = BUILDING_FRAME_SIZE
            if self._source is None:
                source = tk.PhotoImage(file=str(self.path), master=self.canvas)
                if (source.width(), source.height()) != (fw*len(BUILDING_FRAMES), fh):
                    raise ValueError('Invalid architecture atlas dimensions')
                self._source = source
            tw = max(1, round(fw*cell_size/BUILDING_SOURCE_CELL_SIZE))
            th = max(1, round(fh*cell_size/BUILDING_SOURCE_CELL_SIZE))
            sx = BUILDING_FRAMES.index((name, turns % 2))*fw
            photo = crop_scaled(self._source, (sx, 0, fw, fh), (tw, th),
                                master=self.canvas)
            self._cache[key] = photo
            return photo
        except (OSError, ValueError, RuntimeError, tk.TclError):
            self._unavailable = True
            return None

    def clear_cache(self):
        self._cache.clear()
