"""Original 2D terrain texture composition for Tk's map view.

The pixels, variants and 2x2 neighbor masks are exactly the same source
material as the Qt 2D Player. PNG encoding uses only Python's stdlib.
No Pillow, Tk, or Qt import is needed for image generation or testing.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from struct import pack
from zlib import compress, crc32

from drawtemp.assets.topdown_tileset import tile_rgba
from drawtemp.render.autotile2d import (
    MATERIALS, QUADRANTS, QUARTER_SIZE, TILE_SIZE,
    decode_key, mask_alpha, overlays_for_key, tile_key,
)

PNG_HEADER = b"\x89PNG\r\n\x1a\n"
QUADRANT_ORIGINS = ((0, 0), (QUARTER_SIZE, 0),
                    (0, QUARTER_SIZE), (QUARTER_SIZE, QUARTER_SIZE))


def _chunk(tag, payload):
    return (pack(">I", len(payload)) + tag + payload +
            pack(">I", crc32(tag + payload) & 0xffffffff))


def png_rgba(pixels, width=TILE_SIZE, height=TILE_SIZE):
    """Encode a correctly sized RGBA sprite as in-memory PNG bytes."""
    if len(pixels) != width * height * 4:
        raise ValueError("Invalid sprite byte count")
    stride = width * 4
    raw = b"".join(b"\0" + pixels[y * stride:(y + 1) * stride]
                   for y in range(height))
    return (PNG_HEADER +
            _chunk(b"IHDR", pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) +
            _chunk(b"IDAT", compress(raw, 6)) +
            _chunk(b"IEND", b""))


@lru_cache(maxsize=512)
def compose_tile_rgba(key):
    """Per-quadrant land transition, ordered by canonical Qt priorities."""
    center, _neighbors, variant = decode_key(key)
    result = bytearray(tile_rgba(center, variant))
    for (ox, oy), quadrant, overlays in zip(
            QUADRANT_ORIGINS, QUADRANTS, overlays_for_key(key)):
        for overlay in overlays:
            incoming = tile_rgba(overlay.material, variant)
            for local_y in range(QUARTER_SIZE):
                for local_x in range(QUARTER_SIZE):
                    alpha = mask_alpha(quadrant, overlay.mask, local_x, local_y)
                    if not alpha:
                        continue
                    p = ((oy + local_y) * TILE_SIZE + ox + local_x) * 4
                    inv = 255 - alpha
                    for channel in (0, 1, 2):
                        result[p + channel] = (
                            incoming[p + channel] * alpha +
                            result[p + channel] * inv + 127) // 255
    return bytes(result)


@lru_cache(maxsize=512)
def autotile_png(key):
    return png_rgba(compose_tile_rgba(key))


@lru_cache(maxsize=768)
def overlay_png(material, mask, variant, opacity):
    """Mask four independent corners and retain transparent pixels."""
    if (material not in MATERIALS or type(mask) is not tuple or len(mask) != 4
            or any(type(a) is not int or not 0 <= a <= 255 for a in mask)
            or type(opacity) is not int or not 0 <= opacity <= 100
            or type(variant) is not int or variant not in (0, 1)):
        raise ValueError("Invalid authored 2D visual layer")
    pixels = bytearray(tile_rgba(material, variant))
    for i, (ox, oy) in enumerate(QUADRANT_ORIGINS):
        alpha = mask[i] * opacity // 100
        for y in range(oy, oy + QUARTER_SIZE):
            for x in range(ox, ox + QUARTER_SIZE):
                pixels[(y * TILE_SIZE + x) * 4 + 3] = alpha
    return png_rgba(pixels)


class BoardTileIndex:
    """Sparse tactical Board adapter for the same 8-neighbor Qt tile_key."""
    def __init__(self, board):
        self.board = board

    def get(self, cell):
        if not self.board.contains(cell):
            return None
        tile = self.board.tile(cell)
        return {"surface": tile.surface, "height": tile.height}


def key_for_board(board, cell):
    return tile_key(BoardTileIndex(board), *cell)


class TopdownTkAtlas:
    """Canvas-lifetime PhotoImage cache: never evict displayed Tk images.

    A full repaint starts with canvas.delete('all') and *then* clears images.
    Once the budget is reached, additional terrain topology keys fall back
    to their 16 shared base tiles, rather than evicting referenced images.
    """
    def __init__(self, canvas, *, max_images=1536):
        self.canvas = canvas
        self.max_images = max(32, int(max_images))
        self.images = {}
        self._base_images = {}

    def begin_frame(self):
        self.images.clear()
        self._base_images.clear()

    def _photo(self, png, size):
        import tkinter as tk
        from .tk_images import resize_photo
        try:
            photo = tk.PhotoImage(
                master=self.canvas,
                data=base64.b64encode(png).decode("ascii"), format="png")
            return resize_photo(photo, size, size, master=self.canvas)
        except tk.TclError as exc:
            # Old Tcl/Tk or missing image formats should preserve vector map.
            raise ValueError("Tk cannot decode the 2D terrain PNG") from exc

    def terrain(self, key, size):
        if (key, size) in self.images:
            return self.images[key, size]
        center, _neighbors, variant = decode_key(key)
        if len(self.images) >= self.max_images:
            return self.base(center, variant, size)
        try:
            photo = self._photo(autotile_png(key), size)
        except (ImportError, RuntimeError, ValueError, OSError):
            return None
        self.images[key, size] = photo
        return photo

    def base(self, material, variant, size):
        key = material, variant, size
        if key not in self._base_images:
            try:
                self._base_images[key] = self._photo(
                    png_rgba(tile_rgba(material, variant)), size)
            except (ImportError, RuntimeError, ValueError, OSError):
                return None
        return self._base_images[key]

    def layer(self, material, mask, variant, opacity, size):
        key = ("layer", material, tuple(mask), variant, opacity, size)
        if key in self.images:
            return self.images[key]
        if len(self.images) >= self.max_images:
            return None
        try:
            photo = self._photo(overlay_png(material, tuple(mask), variant,
                                             opacity), size)
        except (ImportError, RuntimeError, ValueError, OSError):
            return None
        self.images[key] = photo
        return photo


__all__ = ["png_rgba", "compose_tile_rgba", "autotile_png",
           "overlay_png", "BoardTileIndex", "key_for_board", "TopdownTkAtlas"]
