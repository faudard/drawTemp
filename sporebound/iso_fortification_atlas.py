"""Original pixel-art fortification atlas (remparts, stairs, bridges).

Pure data until sprite() is requested; no Pillow or Tk dependency in the
game engine, Content serializer or tests that operate headlessly.
"""
from pathlib import Path

from .tk_images import crop_scaled

FORTIFICATION_FRAMES = (
    ('Rempart', 0), ('Rempart', 1),
    ('Escalier', 0), ('Escalier', 1),
    ('Pont', 0), ('Pont', 1),
)
FORTIFICATION_FRAME_SIZE = (450, 250)
FORTIFICATION_SOURCE_CELL_SIZE = 36
FORTIFICATION_ROOF_NORTH = (210, 24)
DEFAULT_FORTIFICATION_ATLAS = (Path(__file__).parent / 'content' / 'art'
                               / 'iso' / 'fortifications.png')


def fortification_sprite_top_left(geo, instance):
    """Align the upper vertex of the frame to the same tactical footprint."""
    from .iso_architecture import architecture_outline
    level = 2 if instance.name == 'Rempart' else 0
    north = architecture_outline(geo, instance, wall_level=level)[0][0]
    scale = geo.cell_size / FORTIFICATION_SOURCE_CELL_SIZE
    return (north[0]-FORTIFICATION_ROOF_NORTH[0]*scale,
            north[1]-FORTIFICATION_ROOF_NORTH[1]*scale)


class IsoFortificationAtlas:
    """Transparent cached Tk frames; missing/corrupt asset means no sprite."""
    def __init__(self, canvas, path=DEFAULT_FORTIFICATION_ATLAS):
        self.canvas = canvas
        self.path = Path(path)
        self._source = None
        self._cache = {}
        self._unavailable = False

    def sprite(self, name, turns, cell_size):
        if (self._unavailable or type(turns) is not int
                or type(cell_size) is not int or cell_size < 1
                or (name, turns % 2) not in FORTIFICATION_FRAMES):
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
            fw, fh = FORTIFICATION_FRAME_SIZE
            if self._source is None:
                source = tk.PhotoImage(file=str(self.path), master=self.canvas)
                if (source.width(), source.height()) != (fw*len(FORTIFICATION_FRAMES), fh):
                    raise ValueError('Invalid fortification atlas dimensions')
                self._source = source
            tw = max(1, round(fw*cell_size/FORTIFICATION_SOURCE_CELL_SIZE))
            th = max(1, round(fh*cell_size/FORTIFICATION_SOURCE_CELL_SIZE))
            sx = FORTIFICATION_FRAMES.index((name, turns % 2))*fw
            photo = crop_scaled(self._source, (sx, 0, fw, fh), (tw, th),
                                master=self.canvas)
            self._cache[key] = photo
            return photo
        except (OSError, ValueError, RuntimeError, tk.TclError):
            self._unavailable = True
            return None

    def clear_cache(self):
        self._cache.clear()
