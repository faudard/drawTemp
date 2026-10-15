"""R5.6 editor-only map layer workspace, backed by the existing sidecar.

Content/GameProject remain canonical. Visibility/opacity only affect the Qt
viewport; locks are checked against the *actual* Content diff of each edit.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from sporebound.map_layer_workspace import (
    LAYERS, empty_views, ensure_unlocked, load_views, save_views,
    update_view, view_for,
)
from sporebound.model import RuleError, require


class LayerWorkspace:
    """Per-mission layer preferences; independent of undo and game saves.

    The legacy v1 sidecar persists visibility, locks and active level.
    Opacity is deliberately presentation-only and session-scoped until the
    sidecar receives an explicit versioned schema migration.
    """

    def __init__(self, *, content_path=None):
        self.path = Path(content_path) if content_path is not None else None
        self._views = load_views(self.path) if self.path else empty_views()
        self._opacity = {}
        self._saved = deepcopy(self._views)

    def view(self, mission_id):
        current = view_for(self._views, mission_id)
        current["opacity"] = deepcopy(self._opacity.get(mission_id, {
            name: 100 for name in LAYERS
        }))
        return current

    def set_visible(self, mission_id, layer, visible):
        require(layer in LAYERS, "Unknown layer")
        require(type(visible) is bool, "Visibility must be boolean")
        self._views = update_view(self._views, mission_id, visible={layer: visible})
        return self.view(mission_id)

    def set_locked(self, mission_id, layer, locked):
        require(layer in LAYERS, "Unknown layer")
        require(type(locked) is bool, "Lock must be boolean")
        self._views = update_view(self._views, mission_id, locked={layer: locked})
        return self.view(mission_id)

    def set_level(self, mission_id, level):
        require(type(level) is int and 0 <= level <= 3,
                "Active level must be 0..3")
        self._views = update_view(self._views, mission_id, active_level=level)
        return self.view(mission_id)

    def set_opacity(self, mission_id, layer, opacity):
        require(layer in LAYERS, "Unknown layer")
        require(type(opacity) is int and 0 <= opacity <= 100,
                "Opacity must be 0..100")
        self._opacity.setdefault(mission_id, {name: 100 for name in LAYERS})
        self._opacity[mission_id][layer] = opacity
        return self.view(mission_id)

    def assert_editable(self, before, after):
        """No locked domain may change, even via smart tools or prefabs."""
        return ensure_unlocked(before, after, self._views)

    @property
    def dirty(self):
        return self._views != self._saved

    def save(self, content_path=None):
        destination = Path(content_path) if content_path is not None else self.path
        if destination is None:
            raise RuleError("Save the project before persisting workspace layers")
        save_views(destination, self._views)
        self.path = destination
        self._saved = deepcopy(self._views)
        return destination

    def discard(self):
        self._views = load_views(self.path) if self.path else empty_views()
        self._opacity.clear()
        self._saved = deepcopy(self._views)


__all__ = ["LayerWorkspace", "LAYERS"]
