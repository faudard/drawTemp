"""R7 runtime adapter: published character packs for the shared R3 Qt renderer.

This is presentation-only: never writes Content/GameProject, save slots or CT.
The published pack uses the existing AssetRegistry v1 plus R7 character.json.
No Pillow, Qt, Tk, animation timers or filesystem writes at runtime.
"""
from __future__ import annotations

import json
from pathlib import Path

from sporebound.assets import AssetRegistry
from drawtemp.assets.resolver import AssetResolver
from drawtemp.assets.characters import ACTIONS, DIRECTIONS, CharacterError, _identifier


class CharacterPack:
    """Read-only, validated, cached frame resources from an R7 export."""

    def __init__(self, directory):
        root = Path(directory).resolve(strict=True)
        if not root.is_dir():
            raise CharacterError("Character pack must be a directory")
        meta = json.loads((root / "character.json").read_text(encoding="utf-8"))
        if not isinstance(meta, dict) or meta.get("version") != 1:
            raise CharacterError("Unsupported character pack metadata")
        _identifier(meta.get("character_id"), "character id")
        size, pivot = meta.get("size"), meta.get("pivot")
        if (not isinstance(size, list) or len(size) != 2
                or any(type(x) is not int or not 1 <= x <= 2048 for x in size)
                or not isinstance(pivot, list) or len(pivot) != 2
                or any(type(x) is not int for x in pivot)
                or not 0 <= pivot[0] < size[0] or not 0 <= pivot[1] < size[1]):
            raise CharacterError("Invalid exported canvas size or foot pivot")
        variants = meta.get("variants")
        if not isinstance(variants, list) or not 1 <= len(variants) <= 32:
            raise CharacterError("Character pack needs a list of outfits")
        for variant in variants:
            _identifier(variant, "outfit id")
        if len(set(variants)) != len(variants):
            raise CharacterError("Duplicate outfit id")
        if meta.get("directions") != list(DIRECTIONS):
            raise CharacterError("Unsupported directional metadata")
        data = json.loads((root / "registry.json").read_text(encoding="utf-8"))
        registry = AssetRegistry(data)
        errors = registry.diagnostics(root)
        if errors:
            raise CharacterError("Invalid character asset: " + str(errors[0]))
        self.root = root
        self.character_id = meta["character_id"]
        self.variants = tuple(variants)
        self.pivot = tuple(pivot)
        self.canvas = tuple(size)
        self.registry = registry
        resolver = AssetResolver(registry, root)
        self._clips = {}
        self._files = {}
        for variant in variants:
            for action in ACTIONS:
                for direction in DIRECTIONS:
                    animation_id = (
                        f"anim_{self.character_id}_{variant}_{action}_{direction}"
                    )
                    try:
                        entry = registry.require_reference(animation_id, "animation")
                    except Exception:
                        continue
                    frames = []
                    for sprite in entry["frames"]:
                        asset_id = sprite["sprite"]
                        if asset_id not in self._files:
                            resource = resolver.resolve(asset_id)
                            # Compositor exports one canvas size and one foot pivot
                            # for every pose; never guess dimensions in QML.
                            if resource.region[2:] != self.canvas:
                                raise CharacterError("Character frame/canvas size mismatch")
                            self._files[asset_id] = {
                                "spriteUrl": resource.filename.as_uri(),
                                "spriteRegion": list(resource.region),
                                "spritePivot": list(self.pivot),
                                "spriteReady": True,
                            }
                        frames.append((asset_id, sprite["duration_ms"]))
                    self._clips[(variant, action, direction)] = (
                        entry["loop"], tuple(frames), sum(ms for _, ms in frames))
        if not self._clips:
            raise CharacterError("No valid directional animation in character pack")

    def duration(self, variant, action, direction):
        """Milliseconds; missing artwork never silently mirrors another side."""
        clip = self._clips.get((variant, action, direction))
        return clip[2] if clip else 0

    def sample(self, *, variant, action, direction, elapsed_ms=0):
        """Return one immutable-by-copy QML record, or None for unpainted art."""
        if (type(elapsed_ms) is not int or elapsed_ms < 0
                or direction not in DIRECTIONS or action not in ACTIONS
                or variant not in self.variants):
            raise CharacterError("Invalid visual animation selection")
        clip = self._clips.get((variant, action, direction))
        if clip is None:
            return None
        loop, frames, duration = clip
        t = elapsed_ms % duration if loop else min(elapsed_ms, duration - 1)
        for asset_id, span in frames:
            if t < span:
                return dict(self._files[asset_id])
            t -= span
        raise AssertionError("Animation timing mismatch")

    def preview_actor(self, actor_id, *, variant=None, action="idle",
                      direction="south", elapsed_ms=0):
        """Map a stable gameplay actor ID to cosmetic art, without mutation."""
        if actor_id != self.character_id:
            return None
        outfit = variant if variant is not None else self.variants[0]
        result = self.sample(variant=outfit, action=action,
                             direction=direction, elapsed_ms=elapsed_ms)
        if result is None and action != "idle":
            result = self.sample(variant=outfit, action="idle",
                                 direction=direction, elapsed_ms=0)
        return result
