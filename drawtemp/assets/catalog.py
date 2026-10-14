"""Headless, stable-ID asset browsing and non-destructive legacy import (R4)."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import unicodedata

from sporebound.assets import AssetRegistry

VALID_ID = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}\Z")
FAMILIES = ("all", "characters", "terrain", "decor", "effects", "audio", "other")


def normalized(value):
    value = unicodedata.normalize("NFD", value.casefold())
    return "".join(c for c in value if unicodedata.category(c) != "Mn")


def asset_family(asset_id, kind):
    name = asset_id.casefold()
    if kind == "sound":
        return "audio"
    if name.startswith(("grass", "dirt", "sand", "water", "stone", "rock", "terrain")):
        return "terrain"
    if name.startswith(("fx", "effect", "smoke", "fire", "vfx", "ambient")):
        return "effects"
    if kind == "portrait" or name.startswith(("jeanne", "wolf", "hero", "actor", "unit")):
        return "characters"
    if kind in ("sprite", "animation"):
        return "decor"
    return "other"


@dataclass(frozen=True)
class AssetCard:
    id: str
    kind: str
    family: str
    collection: str
    label: str
    preview_id: str
    animated: bool
    frame_count: int


class AssetIndex:
    """One view of canonical registry entries; not a second manifest."""

    def __init__(self, registry: AssetRegistry):
        self.registry = registry
        self._entries = {item["id"]: item for item in registry.to_dict()["entries"]}
        used = {frame["sprite"] for item in self._entries.values()
                if item["kind"] == "animation" for frame in item["frames"]}
        self.cards = []
        for item in sorted(self._entries.values(), key=lambda e: e["id"].casefold()):
            asset_id, kind = item["id"], item["kind"]
            # Character atlases should appear as grouped pose animations, not
            # hundreds of raw frame assets; single sprites stay visible.
            if kind == "sprite" and asset_id in used:
                continue
            if kind == "sound":
                preview_id, frame_count = asset_id, 0
            elif kind == "animation":
                preview_id, frame_count = item["frames"][0]["sprite"], len(item["frames"])
            else:
                preview_id, frame_count = asset_id, 1
            segments = asset_id.rsplit(".", 2)
            collection = segments[0] if kind == "animation" and len(segments) == 3 else asset_id
            self.cards.append(AssetCard(
                id=asset_id, kind=kind, family=asset_family(asset_id, kind),
                collection=collection, label=asset_id.replace(".", " · "),
                preview_id=preview_id, animated=kind == "animation", frame_count=frame_count))

    def find(self, query="", family="all", *, favorites=(), recents=()):
        if family not in FAMILIES and family not in ("favorites", "recents"):
            raise ValueError("Unknown asset family")
        words = normalized(query).split()
        favored = set(favorites)
        cards = [c for c in self.cards
                 if (family in ("all", "favorites", "recents") or c.family == family)
                 and (family != "favorites" or c.id in favored)
                 and (family != "recents" or c.id in recents)
                 and all(word in normalized(c.label + " " + c.family) for word in words)]
        if family == "recents":
            position = {asset_id: n for n, asset_id in enumerate(recents)}
            cards.sort(key=lambda card: position[card.id])
        return tuple(cards)

    def frames(self, asset_id):
        item = self.registry.require_reference(asset_id)
        if item["kind"] == "animation":
            return tuple((self.registry.require_reference(frame["sprite"], "sprite"),
                          frame["duration_ms"]) for frame in item["frames"])
        if item["kind"] in ("sprite", "portrait"):
            return ((item, 0),)
        return ()


class BrowserPreferences:
    """Project-local browse state using canonical IDs, never mutates GameProject."""
    LIMIT_RECENTS = 30
    LIMIT_FAVORITES = 256

    def __init__(self, path, favorites=(), recents=()):
        self.path = Path(path)
        self.favorites = {item for item in favorites if isinstance(item, str)
                          and VALID_ID.fullmatch(item)}
        self.recents = []
        for item in recents:
            if isinstance(item, str) and VALID_ID.fullmatch(item) and item not in self.recents:
                self.recents.append(item)
        self.favorites = set(sorted(self.favorites)[:self.LIMIT_FAVORITES])
        self.recents = self.recents[:self.LIMIT_RECENTS]

    @classmethod
    def load(cls, path):
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("version") != 1:
                raise ValueError("Unsupported preferences")
            if not isinstance(payload.get("favorites"), list) or not isinstance(payload.get("recents"), list):
                raise ValueError("Invalid preferences")
            return cls(path, payload["favorites"], payload["recents"])
        except (OSError, ValueError, TypeError):
            return cls(path)

    def store(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump({"version": 1, "favorites": sorted(self.favorites),
                           "recents": self.recents}, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def favorite(self, asset_id):
        self._require(asset_id)
        if asset_id in self.favorites:
            self.favorites.remove(asset_id)
        else:
            if len(self.favorites) >= self.LIMIT_FAVORITES:
                raise ValueError("Favorites capacity reached")
            self.favorites.add(asset_id)
        self.store()

    def visit(self, asset_id):
        self._require(asset_id)
        self.recents = [asset_id] + [item for item in self.recents if item != asset_id]
        self.recents = self.recents[:self.LIMIT_RECENTS]
        self.store()

    @staticmethod
    def _require(asset_id):
        if not isinstance(asset_id, str) or not VALID_ID.fullmatch(asset_id):
            raise ValueError("Invalid asset ID")


def plan_legacy_migration(registry: AssetRegistry, entries: list[dict]):
    """Explicit opt-in migration; preserve IDs, reject ambiguous fields/collisions.

    Existing game manifests are not rewritten. Relative paths remain relative
    to their existing project root and must pass canonical validation.
    """
    data = registry.to_dict()
    if not isinstance(entries, list):
        raise ValueError("Legacy entries must be a list")
    for item in entries:
        if (not isinstance(item, dict) or set(item) != {"id", "kind", "path"}
                or item["kind"] not in ("sprite", "portrait", "sound")):
            raise ValueError("Unsupported legacy asset entry")
        data["entries"].append(deepcopy(item))
    return AssetRegistry(data)
