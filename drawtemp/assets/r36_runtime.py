"""R36.C1: committed-tick R36 sprites through the existing R4/R3 atlas resolver.

Only presentation metadata is decorated. Asset resolution, path security,
atlas annotations and PNG verification reuse the existing R4 implementation.
No wall-clock animation loop or new game state is introduced.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from drawtemp.assets.runtime import PresentationAssets
from drawtemp.assets.atlas import png_dimensions
from sporebound.model import RuleError

MAX_CACHED_SPRITES = 256


class R36PresentationAssets(PresentationAssets):
    """Decorate the R3 actor rows using *already resolved* R36 sprite IDs.

    Actors without an authored R36 sprite keep the existing R4 binding
    fallback. Explicit R36 sprites never change with Qt frame-poll cadence.
    """

    def __init__(self, registry, root, annotations=None):
        super().__init__(registry, root, annotations)
        self.has_animations = False  # R36 always selects frames by committed ticks.
        self._sprite_cache = OrderedDict()
        self._stats = {"resolved": 0, "cache_hits": 0, "invalid": 0}

    def _sprite_resource(self, asset_id):
        if type(asset_id) is not str or not asset_id:
            raise ValueError("R36 actor sprite needs a registered R28 sprite ID")
        cached = self._sprite_cache.get(asset_id)
        if cached is not None:
            try:
                stat = cached.filename.stat()
                if (stat.st_mtime_ns, stat.st_size) == cached.revision:
                    self._sprite_cache.move_to_end(asset_id)
                    self._stats["cache_hits"] += 1
                    return cached
            except OSError:
                pass
            self._sprite_cache.pop(asset_id, None)
        descriptor = self.registry.require_reference(asset_id, "sprite")
        frame = self.resolver.resolve(asset_id)
        # Reuse R4's full CRC/dimension budget checks, even for an atlas
        # region (the R4 resolver only needs dimensions without a region).
        width, height = png_dimensions(frame.filename.read_bytes())
        x, y, w, h = frame.region
        if x + w > width or y + h > height:
            raise ValueError("R36 frame region exceeds the approved PNG atlas")
        self._sprite_cache[asset_id] = frame
        if len(self._sprite_cache) > MAX_CACHED_SPRITES:
            self._sprite_cache.popitem(last=False)
        self._stats["resolved"] += 1
        return frame

    def decorate(self, render_rows, *, elapsed_ms=0):
        if type(elapsed_ms) is not int or elapsed_ms < 0:
            raise ValueError("Invalid R36 presentation time")
        result = []
        for row in render_rows:
            if row.get("kind") != "actor":
                result.append(dict(row))
                continue
            actor = dict(row)
            asset_id = actor.get("spriteId")
            if asset_id is None:
                # Keep non-R36 actors compatible with the original R4 display.
                result.extend(super().decorate([actor], elapsed_ms=0))
                continue
            try:
                frame = self._sprite_resource(asset_id)
                x, y, w, h = frame.region
                actor.update({
                    "imageUrl": frame.filename.as_uri(),
                    "assetId": frame.asset_id,
                    "atlasX": x, "atlasY": y,
                    "frameWidth": w, "frameHeight": h,
                    "pivotX": frame.pivot[0], "pivotY": frame.pivot[1],
                    "spriteReady": True,
                    "imageRevision": list(frame.revision),
                })
            except (OSError, RuntimeError, ValueError, RuleError) as exc:
                actor["assetError"] = str(exc)
                self._stats["invalid"] += 1
            result.append(actor)
        return result

    def diagnostics(self):
        return dict(self._stats, cached=len(self._sprite_cache))
