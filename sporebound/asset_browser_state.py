"""Headless browsing collections for the existing map asset palette.

Only UI preferences live here: no edits to Content, GameProject or the art
registry. Persistent IDs are the IDs already exposed by PaletteEntry.
"""
from __future__ import annotations

import json
from pathlib import Path

FAMILIES = (
    ('terrain', 'Terrains'),
    ('decor', 'Décors'),
    ('characters', 'Personnages'),
    ('structures', 'Structures'),
    ('effects', 'Effets visuels'),
    ('interactions', 'Interactions'),
)
FAMILY_LABELS = dict(FAMILIES)
BROWSER_SCOPES = ('all', 'favorites', 'recents') + tuple(key for key, _ in FAMILIES)
WATERCOLOR_FAMILIES = {
    'jeanne': 'characters',
    'wolf': 'characters',
    'spearman': 'characters',
    'townfolk': 'characters',
    'soldiers': 'characters',
    'bestiary': 'characters',
    'heroes': 'characters',
    'props': 'decor',
    'vfx': 'effects',
}


def family_for(entry, *, watercolor_group=''):
    """Return a family for an existing catalog entry (never a new asset kind)."""
    kind = entry.kind
    if kind == 'surface':
        return 'terrain'
    if kind == 'feature':
        return 'decor'
    if kind == 'structure':
        return 'structures'
    if kind == 'actor':
        return 'characters'
    if kind == 'object':
        return 'interactions'
    if kind == 'watercolor':
        return WATERCOLOR_FAMILIES.get(watercolor_group, 'decor')
    return 'decor'


def collection_key(entry, *, watercolor_group=''):
    """Bookmark a watercolor character/effect family, not each source frame."""
    if entry.kind == 'watercolor' and watercolor_group:
        return 'watercolor-group:' + watercolor_group
    return entry.id


class AssetBrowserState:
    """Small, bounded, atomic preferences file beside the edited project."""

    MAX_RECENTS = 20
    MAX_FAVORITES = 128

    def __init__(self, favorites=(), recents=(), path=None):
        self.path = Path(path) if path is not None else None
        self.favorites = set(self._clean_ids(favorites, self.MAX_FAVORITES))
        self.recents = list(self._clean_ids(recents, self.MAX_RECENTS))

    @staticmethod
    def _clean_ids(values, limit):
        if not isinstance(values, (list, tuple, set)):
            return ()
        seen, unique = set(), []
        for value in values:
            if (isinstance(value, str) and 1 < len(value) <= 256
                    and ':' in value and value not in seen):
                unique.append(value)
                seen.add(value)
                if len(unique) >= limit:
                    break
        return tuple(unique)

    @classmethod
    def load(cls, path=None):
        if path is None:
            return cls()
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('version') != 1:
                return cls(path=path)
            return cls(data.get('favorites', ()), data.get('recents', ()),
                       path=path)
        except (OSError, ValueError, TypeError):
            return cls(path=path)

    def save(self):
        """Atomic write; the previous preferences survive a failed replace."""
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + '.tmp')
        payload = {
            'version': 1,
            'favorites': sorted(self.favorites),
            'recents': self.recents[:self.MAX_RECENTS],
        }
        try:
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding='utf-8')
            temp.replace(self.path)
        finally:
            # An interrupted write must not leave a fake loaded preference.
            temp.unlink(missing_ok=True)

    def toggle_favorite(self, key):
        if not self._clean_ids((key,), 1):
            raise ValueError('Invalid asset bookmark ID')
        if key in self.favorites:
            self.favorites.remove(key)
        else:
            if len(self.favorites) >= self.MAX_FAVORITES:
                raise ValueError('Too many asset favorites')
            self.favorites.add(key)
        self.save()
        return key in self.favorites

    def touch(self, key):
        if not self._clean_ids((key,), 1):
            raise ValueError('Invalid recent asset ID')
        self.recents = [key] + [item for item in self.recents if item != key]
        del self.recents[self.MAX_RECENTS:]
        self.save()

    def contains(self, scope, key, family):
        if scope == 'all':
            return True
        if scope == 'favorites':
            return key in self.favorites
        if scope == 'recents':
            return key in self.recents
        return scope == family

    def order(self, scope, entries):
        """Recent items sort newest-first; other views preserve catalog order."""
        if scope != 'recents':
            return tuple(entries)
        order = {key: i for i, key in enumerate(self.recents)}
        return tuple(sorted(entries, key=lambda entry: order.get(entry[0], 999999)))
