"""Qt Quick image provider for native 2D material/quarter-autotile sprites.

One cached 64x64 RGBA image per unique 8-neighbor topology/texture variant;
QML loads only visible keys, and identical neighborhoods share the same art.
The provider owns a bounded LRU, never a texture or QImage per map cell.
"""
from __future__ import annotations

from collections import OrderedDict
from functools import lru_cache
from threading import RLock

from drawtemp.assets.topdown_tileset import atlas_rect, starter_tileset_png
from .autotile2d import (QUADRANTS, QUARTER_SIZE, TILE_SIZE, decode_key,
                         mask_alpha, overlays_for_key)

MAX_ATLAS_IMAGES = 256


def make_topdown_image_provider(max_images=MAX_ATLAS_IMAGES):
    """Optional Qt import; usable by both Map Studio and exported Player."""
    from PySide6.QtCore import Qt, QRect
    from PySide6.QtGui import QImage, QPainter, qRgba
    from PySide6.QtQuick import QQuickImageProvider

    if type(max_images) is not int or not 1 <= max_images <= 4096:
        raise ValueError("Invalid autotile image-cache limit")

    @lru_cache(maxsize=32)
    def alpha_mask(quadrant, bits):
        mask = QImage(QUARTER_SIZE, QUARTER_SIZE, QImage.Format_ARGB32)
        for y in range(QUARTER_SIZE):
            for x in range(QUARTER_SIZE):
                alpha = mask_alpha(quadrant, bits, x, y)
                mask.setPixel(x, y, qRgba(255, 255, 255, alpha))
        return mask

    class AutotileProvider(QQuickImageProvider):
        def __init__(self):
            super().__init__(QQuickImageProvider.Image)
            self.atlas = QImage()
            if not self.atlas.loadFromData(starter_tileset_png(), "PNG"):
                raise RuntimeError("Unable to decode the bundled 2D tileset")
            self.entries = OrderedDict()
            self.lock = RLock()

        @staticmethod
        def _quadrant_origin(quadrant):
            return (QUARTER_SIZE if quadrant in ("ne", "se") else 0,
                    QUARTER_SIZE if quadrant in ("sw", "se") else 0)

        def _render(self, key):
            material, _, variant = decode_key(key)
            tile = QImage(TILE_SIZE, TILE_SIZE, QImage.Format_ARGB32)
            tile.fill(Qt.transparent)
            painter = QPainter(tile)
            source_x, _, _, _ = atlas_rect(material, variant)
            painter.drawImage(QRect(0, 0, TILE_SIZE, TILE_SIZE),
                              self.atlas, QRect(source_x, 0, TILE_SIZE, TILE_SIZE))
            for quadrant, layers in zip(QUADRANTS, overlays_for_key(key)):
                qx, qy = self._quadrant_origin(quadrant)
                for overlay in layers:
                    patch = QImage(QUARTER_SIZE, QUARTER_SIZE, QImage.Format_ARGB32)
                    patch.fill(Qt.transparent)
                    patch_painter = QPainter(patch)
                    incoming_x, _, _, _ = atlas_rect(overlay.material, variant)
                    patch_painter.drawImage(
                        QRect(0, 0, QUARTER_SIZE, QUARTER_SIZE),
                        self.atlas, QRect(incoming_x + qx, qy,
                                          QUARTER_SIZE, QUARTER_SIZE))
                    patch_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
                    patch_painter.drawImage(0, 0, alpha_mask(quadrant, overlay.mask))
                    patch_painter.end()
                    painter.drawImage(qx, qy, patch)
            painter.end()
            return tile

        def requestImage(self, image_id, size, requestedSize):
            try:
                decode_key(image_id)
            except ValueError:
                return QImage()  # malformed or stale image URL
            with self.lock:
                tile = self.entries.get(image_id)
                if tile is None:
                    tile = self._render(image_id)
                    self.entries[image_id] = tile
                    while len(self.entries) > max_images:
                        self.entries.popitem(last=False)
                else:
                    self.entries.move_to_end(image_id)
                if size is not None:
                    size.setWidth(TILE_SIZE)
                    size.setHeight(TILE_SIZE)
                return tile

    return AutotileProvider()
