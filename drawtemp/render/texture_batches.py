"""R3.D: bounded, invalidatable terrain texture batches for the shared Qt viewport.

Only simple flat static tiles are baked; relief, props, tactical states, actors,
and architectural surfaces keep their accurate, individually sorted QML nodes.
Painting uses QImage on CPU; Qt Quick uploads/composites resulting chunk textures.
This is NOT OpenGL/Vulkan instancing nor proof of GPU frame-time performance.
"""
from collections import OrderedDict
from math import ceil, floor
from pathlib import Path

from .iso_scene import IsoProjection, MATERIALS, COLORS

BATCH_SIDE = 8
MAX_PIXELS = 2048 * 2048
DEFAULT_BUDGET = 64 * 1024 * 1024


def is_static_tile(row):
    """Use the batch only for tiles whose layered renderer is unnecessary."""
    return (row.get("kind") == "tile" and row.get("height") == 0
            and not row.get("eastDrop") and not row.get("southDrop")
            and not row.get("feature") and not row.get("blocked")
            and not row.get("cover") and not row.get("hazard")
            and not row.get("goal"))


def chunk_key(x, y):
    return x // BATCH_SIDE, y // BATCH_SIDE


class BoundedImageStore:
    """LRU of immutable QImages, sized by raw RGBA bytes (not PNG bytes)."""
    def __init__(self, budget=DEFAULT_BUDGET):
        if type(budget) is not int or budget <= 0:
            raise ValueError("Budget must be positive bytes")
        self.budget = budget
        self._entries = OrderedDict()
        self.used_bytes = 0
        self.hits = 0
        self.misses = 0

    def get(self, key):
        image = self._entries.get(key)
        if image is None:
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        return image

    def put(self, key, image):
        size = image.width() * image.height() * 4
        if size > self.budget:
            return False
        self.drop(key)
        while self.used_bytes + size > self.budget:
            _, old = self._entries.popitem(last=False)
            self.used_bytes -= old.width() * old.height() * 4
        self._entries[key] = image
        self.used_bytes += size
        return True

    def drop(self, key):
        old = self._entries.pop(key, None)
        if old is not None:
            self.used_bytes -= old.width() * old.height() * 4

    def clear(self):
        self._entries.clear()
        self.used_bytes = 0


class TerrainTextureBatches:
    """Per-viewport provider data and stable, versioned batch identifiers.

    _source caches input art for this atlas generation. _store caches rendered
    QImages; it is safe to evict because QQuick keeps its own uploaded texture.
    """
    def __init__(self, index, *, atlas_url="", budget=DEFAULT_BUDGET):
        self.index = index
        self.store = BoundedImageStore(budget)
        self.atlas_url = atlas_url
        self._atlas = None
        self.generations = {}
        self.entries = {}  # image ID -> immutable cached QImage
        self.pending = {}
        self.last_visible = []
        self._epoch = 0
        self._source = None

    def reset(self, index):
        self.index = index
        self._epoch += 1
        self.generations.clear()
        self.entries.clear()
        self.pending.clear()
        self.store.clear()
        self.last_visible = []
        self._atlas = None
        self._source = None

    def invalidate(self, dirty):
        """Dirty cells also affect side-face adjacency in neighboring chunks."""
        touched = set()
        for x, y in dirty:
            for cell in ((x, y), (x-1, y), (x, y-1)):
                if cell[0] >= 0 and cell[1] >= 0:
                    touched.add(chunk_key(*cell))
        for chunk in touched:
            self.generations[chunk] = self.generations.get(chunk, 0) + 1
            self.store.drop(chunk)
        return touched

    def set_atlas(self, url):
        if url != self.atlas_url:
            self.atlas_url = url
            self.reset(self.index)

    def _atlas_image(self):
        if self._source != self.atlas_url:
            from PySide6.QtGui import QImage
            from PySide6.QtCore import QUrl
            path = QUrl(self.atlas_url).toLocalFile() if self.atlas_url else ""
            self._atlas = QImage(path) if path and Path(path).is_file() else QImage()
            self._source = self.atlas_url
        return self._atlas

    def _source_tiles(self, chunk):
        """Read all eligible tiles in a chunk, independent of camera visibility."""
        bucket = self.index.chunks.get(chunk, {})
        elevations = self.index.elevations
        output = []
        for (x, y), tile in bucket.items():
            if (tile.get("height", 0) != 0 or tile.get("feature")
                    or tile.get("blocked") or tile.get("cover")
                    or tile.get("hazard") or tile.get("goal")
                    or elevations.get((x+1, y), 0) < 0
                    or elevations.get((x, y+1), 0) < 0):
                continue
            output.append(tile)
        return sorted(output, key=lambda t: (t["x"]+t["y"], t["x"], t["y"]))

    def _raster(self, tiles, origin):
        from PySide6.QtGui import QImage, QColor, QPainter, QPen, QPolygonF
        from PySide6.QtCore import QPointF, QRectF, Qt
        atlas = self._atlas_image()
        sx, sy, width, height = origin
        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, False)
        projection = IsoProjection()
        for t in tiles:
            x, y = t["x"], t["y"]
            px, py = projection.project(x, y)
            px, py = px - sx, py - sy
            poly = QPolygonF([QPointF(px, py-24), QPointF(px+48, py),
                              QPointF(px, py+24), QPointF(px-48, py)])
            surface = t["surface"] if t["surface"] in MATERIALS else "grass"
            painter.setPen(QPen(QColor("#283b3d"), 0.8))
            painter.setBrush(QColor(COLORS[MATERIALS.index(surface)]))
            painter.drawPolygon(poly)
            if not atlas.isNull():
                atlas_col = MATERIALS.index(surface)*2 + ((x*17+y*29)&1)
                painter.drawImage(QRectF(px-48, py-24, 96, 48), atlas,
                                  QRectF(atlas_col*96, 0, 96, 48))
        painter.end()
        return image

    def prepare(self, visible_rows):
        """Generate textures only for changed/uncached visible chunk contents.

        Returns (image rows, IDs of tiled cells replaced by textures).
        When a chunk exceeds resource limits, original tile nodes remain.
        """
        requested = set()
        for row in visible_rows:
            if is_static_tile(row):
                requested.add(chunk_key(row["x"], row["y"]))
        descriptors, replaced = [], set()
        p = IsoProjection()
        self.entries.clear()
        for chunk in sorted(requested):
            tiles = self._source_tiles(chunk)
            if not tiles:
                continue
            centers = [p.project(t["x"], t["y"]) for t in tiles]
            x0 = floor(min(x for x, _ in centers) - 48) - 1
            y0 = floor(min(y for _, y in centers) - 24) - 1
            x1 = ceil(max(x for x, _ in centers) + 48) + 1
            y1 = ceil(max(y for _, y in centers) + 24) + 1
            width, height = x1-x0, y1-y0
            if (width*height > MAX_PIXELS or width*height*4 > self.store.budget):
                continue
            image = self.store.get(chunk)
            if image is None:
                image = self._raster(tiles, (x0, y0, width, height))
                if not self.store.put(chunk, image):
                    continue
            image_id = ("%d/%d/%d/%d" % (
                self._epoch, chunk[0], chunk[1],
                self.generations.get(chunk, 0)))
            # QQuick image provider needs an immutable backing image while it
            # is requested. If evicted later, the scenegraph owns its texture.
            self.entries[image_id] = image
            descriptors.append({"id": image_id, "sx": x0, "sy": y0,
                                "width": width, "height": height,
                                "url": "image://drawtemp-tiles/" + image_id,
                                "zOrder": -1})
            replaced.update(("tile:%d:%d" % (t["x"], t["y"]) for t in tiles))
        self.last_visible = descriptors
        return descriptors, replaced


def make_image_provider(batches):
    """QQuick image provider; call only after Qt is installed."""
    from PySide6.QtQuick import QQuickImageProvider
    from PySide6.QtGui import QImage

    class BatchProvider(QQuickImageProvider):
        def __init__(self):
            super().__init__(QQuickImageProvider.Image)

        def requestImage(self, image_id, size, requestedSize):
            # A stale QML request after a map switch returns transparent art.
            result = batches.entries.get(image_id)
            if result is None:
                return QImage()
            if size is not None:
                size.setWidth(result.width())
                size.setHeight(result.height())
            return result

    return BatchProvider()
