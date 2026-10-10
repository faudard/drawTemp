"""Portable presentation assets. No renderer, decoding, or gameplay dependencies.

IDs are stable; paths are relative to the game manifest, never the process cwd.
Animations reference sprites and durations, rather than executable callbacks.
"""
from copy import deepcopy
from pathlib import Path, PureWindowsPath
import re

from .model import RuleError, require

KINDS = ('sprite', 'portrait', 'sound', 'animation')
EXTENSIONS = {'sprite': {'.png'}, 'portrait': {'.png'},
              'sound': {'.wav', '.ogg'}}


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}', value)


def _portable_path(value):
    require(isinstance(value, str) and bool(value), 'Asset path must be a string')
    require(not PureWindowsPath(value).drive and not value.startswith('/') and
            '\\' not in value and all(part not in ('', '.', '..') for part in value.split('/')),
            f'Asset path must be project-relative: {value}')
    for part in value.split('/'):
        require(not any(ord(c) < 32 or c in '<>:"|?*' for c in part) and
                not part.endswith((' ', '.')) and
                part.split('.')[0].upper() not in
                {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
                 *(f'LPT{i}' for i in range(1, 10))}, f'Non-portable asset path: {value}')


class AssetRegistry:
    """Validated immutable-by-copy manifest with typed presentation bindings.

    Filesystem validation is explicit, so replay/headless machines do not need
    artwork. Binding slots are presentation-owned names (e.g. hero or title).
    """
    def __init__(self, data=None):
        if data is None:
            data = {'version': 1, 'entries': [], 'bindings': {}}
        require(isinstance(data, dict) and set(data) == {'version', 'entries', 'bindings'},
                'Assets need version, entries and bindings')
        require(type(data['version']) is int and data['version'] == 1,
                'Unsupported asset registry version')
        require(isinstance(data['entries'], list), 'Asset entries must be a list')
        require(isinstance(data['bindings'], dict), 'Asset bindings must be an object')
        self._data = deepcopy(data)
        self._entries = {}
        folded = set()
        for entry in self._data['entries']:
            require(isinstance(entry, dict), 'Asset entry must be an object')
            aid, kind = entry.get('id'), entry.get('kind')
            require(_identifier(aid), 'Invalid asset id')
            require(aid.casefold() not in folded, f'Duplicate asset id: {aid}')
            require(isinstance(kind, str) and kind in KINDS, f'{aid}: invalid asset kind')
            fields = {'id', 'kind', 'frames', 'loop'} if kind == 'animation' else {'id', 'kind', 'path'}
            require(set(entry) == fields, f'{aid}: unknown or missing asset fields')
            if kind != 'animation':
                _portable_path(entry['path'])
                require(Path(entry['path']).suffix.lower() in EXTENSIONS[kind],
                        f'{aid}: unsupported {kind} extension')
            else:
                require(type(entry['loop']) is bool, f'{aid}: loop must be boolean')
                require(isinstance(entry['frames'], list) and 0 < len(entry['frames']) <= 10000,
                        f'{aid}: animation needs 1..10000 frames')
                for frame in entry['frames']:
                    require(isinstance(frame, dict) and set(frame) == {'sprite', 'duration_ms'},
                            f'{aid}: frame needs sprite and duration_ms')
                    require(type(frame['duration_ms']) is int and 1 <= frame['duration_ms'] <= 60000,
                            f'{aid}: frame duration must be 1..60000 ms')
            self._entries[aid] = entry
            folded.add(aid.casefold())
        # Second pass permits forward references; animation cycles are impossible.
        for entry in self._entries.values():
            if entry['kind'] == 'animation':
                for frame in entry['frames']:
                    self.require_reference(frame['sprite'], 'sprite')
        for kind, slots in self._data['bindings'].items():
            require(kind in KINDS and isinstance(slots, dict), 'Invalid asset binding group')
            for slot, aid in slots.items():
                require(_identifier(slot), 'Invalid presentation slot')
                self.require_reference(aid, kind)

    def to_dict(self):
        return deepcopy(self._data)

    def require_reference(self, asset_id, kind=None):
        require(isinstance(asset_id, str) and asset_id in self._entries,
                f'Unknown asset reference: {asset_id}')
        entry = self._entries[asset_id]
        require(kind is None or entry['kind'] == kind,
                f'{asset_id}: expected {kind}, got {entry["kind"]}')
        return deepcopy(entry)

    def binding(self, kind, slot):
        """Return an optional asset descriptor for a presentation slot."""
        require(kind in KINDS, 'Unknown asset kind')
        aid = self._data['bindings'].get(kind, {}).get(slot)
        return self.require_reference(aid, kind) if aid is not None else None

    def resolve(self, asset_id, root):
        """Resolve an existing file without allowing symlink escape from root."""
        entry = self.require_reference(asset_id)
        require(entry['kind'] != 'animation', 'Animations have frames, not a file path')
        root = Path(root).resolve()
        try:
            path = (root / entry['path']).resolve()
            require(path.is_relative_to(root), f'{asset_id}: asset escapes project root')
            require(path.is_file(), f'{asset_id}: missing asset file: {entry["path"]}')
            # Check exact spelling even on case-insensitive development machines.
            current = root
            for part in entry['path'].split('/'):
                require(part in {child.name for child in current.iterdir()},
                        f'{asset_id}: asset path case mismatch: {entry["path"]}')
                current = current / part
            return path
        except (OSError, RuntimeError) as exc:
            raise RuleError(f'{asset_id}: cannot resolve asset: {exc}') from exc

    def diagnostics(self, root):
        """Collect file errors in ID order, instead of hiding all but the first."""
        issues = []
        for aid, entry in sorted(self._entries.items()):
            if entry['kind'] == 'animation':
                continue
            try:
                path = self.resolve(aid, root)
                with path.open('rb') as source:
                    header = source.read(12)
                suffix = Path(entry['path']).suffix.lower()
                valid = (header.startswith(b'\x89PNG\r\n\x1a\n') if suffix == '.png' else
                         header.startswith(b'OggS') if suffix == '.ogg' else
                         header.startswith(b'RIFF') and header[8:12] == b'WAVE')
                require(valid, f'{aid}: invalid {suffix} file signature')
            except (RuleError, OSError) as exc:
                issues.append({'asset_id': aid, 'message': str(exc)})
        return issues
