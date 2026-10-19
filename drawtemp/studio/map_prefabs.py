"""R22.2B: reusable terrain-only prefab shelf (no separate gameplay schema).

Group/actor prefabs remain the responsibility of the existing R6/group-prefab
tools. This shelf stores just canonical TerrainClipboard cells and goals,
delegating placement safety, revision leases and Undo to R5 MapSelection.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from drawtemp.core import RuleError
from sporebound.map_authoring import TerrainClipboard
from sporebound.map_transform import _validate_clipboard, transform_terrain
from .map_selection import RegionStamp, MAX_SELECTION


FILE_KIND = "drawtemp-r22-terrain-prefabs"
VERSION = 1
MAX_CUSTOM = 64
MAX_BYTES = 2 * 1024 * 1024
ORIENTATIONS = ("none", "rotate_cw", "rotate_ccw", "mirror_x", "mirror_y")


def _recipe(width, height, rows):
    offsets, terrain = [], []
    for x, y, surface, feature in rows:
        offsets.append((x, y))
        tile = {"surface": surface}
        if surface == "water":
            tile["blocked"] = True
        if feature:
            tile["feature"] = feature
        if feature == "stone_wall":
            tile["blocked"] = True
        terrain.append(tile)
    return _validate_clipboard(TerrainClipboard(
        width, height, tuple(offsets), tuple(terrain), ()
    ))


def _builtins():
    return (
        ("builtin:path-cross", "Carrefour pavé", "Chemins",
         _recipe(5, 5, tuple(
             (x, y, "cobble", "") for y in range(5) for x in range(5)
             if x == 2 or y == 2
         ))),
        ("builtin:pond", "Petit étang", "Nature",
         _recipe(5, 5, tuple(
             (x, y, "water" if 1 <= x <= 3 and 1 <= y <= 3 else "sand", "")
             for y in range(5) for x in range(5)
         ))),
        ("builtin:grove", "Bosquet", "Nature",
         _recipe(5, 5, (
             (0, 0, "grass", "tree"), (3, 0, "grass", "tree"),
             (1, 2, "grass", "bush"), (4, 2, "grass", "tree"),
             (0, 4, "grass", "tree"), (3, 4, "grass", "bush"),
         ))),
        ("builtin:camp", "Campement", "Décors",
         _recipe(4, 3, (
             (1, 0, "dirt", "crate"), (2, 0, "dirt", ""),
             (0, 1, "dirt", ""), (1, 1, "dirt", "lantern"),
             (2, 1, "dirt", ""), (3, 1, "dirt", "crate"),
             (1, 2, "dirt", ""), (2, 2, "dirt", ""),
         ))),
    )


@dataclass(frozen=True)
class PrefabEntry:
    key: str
    title: str
    category: str
    stamp: RegionStamp
    builtin: bool


class TerrainPrefabLibrary:
    """Session-local palette; portable user presets require explicit import/export."""

    def __init__(self):
        self._entries = {
            key: PrefabEntry(key, title, category, RegionStamp(clip, "builtin"), True)
            for key, title, category, clip in _builtins()
        }

    def entries(self, query="", category="Tous"):
        if not isinstance(query, str):
            raise RuleError("Search must be text")
        if category not in ("Tous", "Nature", "Chemins", "Décors", "Mes modèles"):
            raise RuleError("Unknown prefab category")
        needle = query.strip().casefold()
        return tuple(entry for entry in self._entries.values()
                     if (category == "Tous" or entry.category == category)
                     and (not needle or needle in
                          (entry.title + " " + entry.category).casefold()))

    def get(self, key, orientation="none"):
        if key not in self._entries:
            raise RuleError("Unknown terrain prefab")
        if orientation not in ORIENTATIONS:
            raise RuleError("Unknown prefab orientation")
        original = self._entries[key].stamp
        clip = deepcopy(original.clip)
        if orientation != "none":
            clip = transform_terrain(clip, orientation)
        return RegionStamp(clip, original.origin_mission)

    def capture(self, title, stamp):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 80:
            raise RuleError("Prefab title must contain 1..80 characters")
        if not isinstance(stamp, RegionStamp):
            raise RuleError("Select and copy a terrain region first")
        clip = deepcopy(_validate_clipboard(stamp.clip))
        if len(clip.offsets) > MAX_SELECTION:
            raise RuleError("Prefab contains more than 4096 cells")
        key = "custom:" + re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
        if key == "custom:" or key in self._entries:
            raise RuleError("Duplicate or unsupported prefab name")
        if sum(not entry.builtin for entry in self._entries.values()) >= MAX_CUSTOM:
            raise RuleError("Prefab shelf is full")
        self._entries[key] = PrefabEntry(
            key, title.strip(), "Mes modèles", RegionStamp(clip, stamp.origin_mission),
            False
        )
        return key

    def _payload(self):
        rows = []
        for entry in self._entries.values():
            if entry.builtin:
                continue
            clip = entry.stamp.clip
            rows.append({
                "name": entry.title,
                "width": clip.width, "height": clip.height,
                "offsets": [list(cell) for cell in clip.offsets],
                "terrain": deepcopy(clip.terrain),
                "goals": [list(cell) for cell in clip.goals],
            })
        return {"kind": FILE_KIND, "version": VERSION, "entries": rows}

    def export_file(self, filename):
        """Atomic create-only export, including when another process races us."""
        path = Path(filename).absolute()
        if not path.parent.is_dir() or path.exists() or path.is_symlink():
            raise RuleError("Choose a new prefab library file in an existing folder")
        raw = (json.dumps(self._payload(), ensure_ascii=False,
                          sort_keys=True, indent=2) + "\n").encode("utf-8")
        if len(raw) > MAX_BYTES:
            raise RuleError("Prefab library exceeds 2 MiB")
        tmp = None
        try:
            with NamedTemporaryFile(prefix=".r22-prefabs-", dir=path.parent,
                                    delete=False) as stream:
                tmp = Path(stream.name)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            # Unlike os.replace, hard-link creation fails if path exists.
            os.link(tmp, path)
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
        return path

    @classmethod
    def import_file(cls, filename):
        """Fail closed on malformed files and never mutate an existing shelf."""
        path = Path(filename)
        if path.stat().st_size > MAX_BYTES:
            raise RuleError("Prefab library exceeds 2 MiB")
        raw = path.read_bytes()
        if len(raw) > MAX_BYTES:
            raise RuleError("Prefab library exceeds 2 MiB")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise RuleError("Invalid prefab library JSON") from exc
        if (type(data) is not dict or set(data) != {"kind", "version", "entries"}
                or data["kind"] != FILE_KIND or type(data["version"]) is not int
                or data["version"] != VERSION or type(data["entries"]) is not list
                or len(data["entries"]) > MAX_CUSTOM):
            raise RuleError("Unsupported prefab library structure")
        shelf = cls()
        for row in data["entries"]:
            if (type(row) is not dict or
                    set(row) != {"name", "width", "height", "offsets", "terrain", "goals"}
                    or type(row["offsets"]) is not list
                    or type(row["terrain"]) is not list
                    or type(row["goals"]) is not list):
                raise RuleError("Invalid prefab entry fields")
            clip = _validate_clipboard(TerrainClipboard(
                row["width"], row["height"], tuple(row["offsets"]),
                tuple(row["terrain"]), tuple(row["goals"])
            ))
            shelf.capture(row["name"], RegionStamp(clip, "imported"))
        return shelf
