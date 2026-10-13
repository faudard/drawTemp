"""Shared read-only watercolor gallery backed by the existing AssetRegistry.

The 88 sprite and 15 animation IDs remain in assets/watercolor/registry.json.
No gameplay fields, second asset format, implicit placeholders or Tk imports.
A missing binary pack is explicitly reported instead of appearing available.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from .assets import AssetRegistry
from .model import RuleError

DEFAULT_WATERCOLOR_ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'watercolor'


@dataclass(frozen=True)
class WatercolorEntry:
    id: str
    kind: str
    group: str
    title: str
    frame_count: int = 1


class WatercolorCatalog:
    """Read-only view used by the Studio and by any future Player art binding."""

    def __init__(self, root=None):
        self.root = Path(root) if root is not None else DEFAULT_WATERCOLOR_ROOT
        self.registry = None
        self._index = {}
        self._sha256 = {}
        self.entries = ()
        index_file = self.root / 'index.json'
        registry_file = self.root / 'registry.json'
        if not index_file.is_file() or not registry_file.is_file():
            # Installed wheels may omit the optional external art bundle.
            return
        index = json.loads(index_file.read_text(encoding='utf-8'))
        registry = AssetRegistry(json.loads(registry_file.read_text(encoding='utf-8')))
        sprites = index.get('sprites', ())
        if (index.get('schema_version') != 1 or
                not isinstance(sprites, list)):
            raise ValueError('Unsupported watercolor index schema')
        found = {}
        entries = []
        for item in sprites:
            if not isinstance(item, dict):
                raise ValueError('Invalid watercolor sprite descriptor')
            asset_id = item['id']
            descriptor = registry.require_reference(asset_id, 'sprite')
            if descriptor['path'] != item['path'] or asset_id in found:
                raise ValueError('Watercolor registry/index mismatch')
            group = item['sheet']
            if not isinstance(group, str) or not group:
                raise ValueError('Missing watercolor group')
            found[asset_id] = item
            entries.append(WatercolorEntry(asset_id, 'sprite', group,
                                          asset_id.replace('_', ' ').capitalize()))
        animations = [item for item in registry.to_dict()['entries']
                      if item['kind'] == 'animation']
        for item in animations:
            group = item['id'].split('_', 2)[1]
            entries.append(WatercolorEntry(item['id'], 'animation', group,
                          item['id'].replace('_', ' ').capitalize(),
                          len(item['frames'])))
        self.registry = registry
        self._index = found
        self.entries = tuple(entries)
        provenance_file = self.root / 'provenance.json'
        if provenance_file.is_file():
            provenance = json.loads(provenance_file.read_text(encoding='utf-8'))
            hashes = provenance.get('sprite_hashes', {})
            if (not isinstance(hashes, dict) or
                    set(hashes) != {item['path'] for item in sprites} or
                    any(not isinstance(v, str) or len(v) != 64
                        for v in hashes.values())):
                raise ValueError('Invalid watercolor provenance index')
            self._sha256 = hashes

    def has_metadata(self):
        return self.registry is not None

    def lookup(self, asset_id):
        for item in self.entries:
            if item.id == asset_id:
                return item
        raise KeyError(asset_id)

    def frame(self, asset_id, frame_index=0):
        """Return a real sprite ID and its authored frame duration.

        No synthesis of missing direction or animation frames.
        """
        item = self.lookup(asset_id)
        if item.kind == 'sprite':
            if frame_index != 0:
                raise IndexError('Static sprite has only one frame')
            return item.id, 0
        animation = self.registry.require_reference(asset_id, 'animation')
        if type(frame_index) is not int or not 0 <= frame_index < len(animation['frames']):
            raise IndexError('Watercolor frame outside animation')
        row = animation['frames'][frame_index]
        return row['sprite'], row['duration_ms']

    def sample(self, asset_id, elapsed_ms):
        """Resolve actual authored animation timing, including held final poses."""
        item = self.lookup(asset_id)
        if item.kind == 'sprite':
            return asset_id, 0
        animation = self.registry.require_reference(asset_id, 'animation')
        total = sum(row['duration_ms'] for row in animation['frames'])
        t = max(0, int(elapsed_ms))
        t = t % total if animation['loop'] else min(t, total - 1)
        for index, row in enumerate(animation['frames']):
            if t < row['duration_ms']:
                return row['sprite'], index
            t -= row['duration_ms']
        raise AssertionError('Validated animation must have a frame')

    def status(self, sprite_id, *, verify=False):
        """Return ('ready'|'missing'|'modified', Path|None).

        Preview never displays modified art as if it were certified.
        Cheap metadata mode supports listing without decoding/hashing 88 PNGs.
        """
        if self.registry is None or sprite_id not in self._index:
            raise KeyError(sprite_id)
        spec = self.registry.require_reference(sprite_id, 'sprite')
        try:
            path = self.registry.resolve(sprite_id, self.root)
        except (RuleError, OSError):
            return 'missing', None
        if verify and self._sha256:
            try:
                with path.open('rb') as source:
                    digest = sha256(source.read()).hexdigest()
                if digest != self._sha256[spec['path']]:
                    return 'modified', None
            except OSError:
                return 'missing', None
        return 'ready', path
