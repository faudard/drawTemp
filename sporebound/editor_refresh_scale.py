"""Safe generation-based projections for large-map Studio refreshes.

No stored identity assumptions: a JSON value fingerprint detects nested in-place
authoring edits and restores. Failed parsing never replaces a valid projection.
Tk-independent for easy deterministic regression tests.
"""
from __future__ import annotations

import json

from .model import Content


class EditorContentProjection:
    def __init__(self):
        self._snapshot = None
        self._model = None
        self.generation = 0
        self.rebuilds = 0

    def get(self, document):
        snapshot = json.dumps(document, sort_keys=True, ensure_ascii=True)
        if self._model is not None and snapshot == self._snapshot:
            return self._model
        model = Content.from_dict(document)
        self._snapshot = snapshot
        self._model = model
        self.generation += 1
        self.rebuilds += 1
        return model

    def invalidate(self):
        self._snapshot = None
        self._model = None


class MinimapBackgroundCache:
    """One scene retained on Canvas, plus a separately refreshed viewport."""

    def __init__(self):
        self._key = None
        self._items = None
        self.full_repaints = 0
        self.viewport_updates = 0

    def needs_background(self, key, canvas):
        return (key != self._key or self._items is None or
                len(canvas.find_all()) != self._items)

    def complete(self, key, canvas, *, background_redrawn):
        if background_redrawn:
            self.full_repaints += 1
            self._key = key
        self.viewport_updates += 1
        self._items = len(canvas.find_all())

    def invalidate(self):
        self._key = self._items = None
