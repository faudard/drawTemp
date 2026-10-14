"""3.7.33B — UI-only, identity-based Workspace navigation.

The history stores resource IDs, never stale coordinates or documents. Resolve
against current Content at navigation time. No gameplay model/schema changes.
"""
from .model import RuleError
from .workspace_shell import map_resource_target, inspect_persistent_group


def map_selection_key(data, mission_id, cell, *, group_id=None, cells=()):
    """Map/Treeview -> stable resource, preserving selection-group identity."""
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    if mission is None:
        raise RuleError('Mission introuvable : ' + mission_id)
    if group_id is not None:
        if not any(g['id'] == group_id for g in mission.get('editor_groups', ())):
            raise RuleError('Groupe introuvable : ' + group_id)
        return f'editor_group:{mission_id}/{group_id}'
    cell = tuple(cell)
    if len(cell) != 2 or not all(type(v) is int for v in cell) or not (
            0 <= cell[0] < mission['board']['width'] and
            0 <= cell[1] < mission['board']['height']):
        raise RuleError('Case hors carte')
    if len({tuple(p) for p in cells}) > 1:
        return f'map_tile:{mission_id}/{cell[0]},{cell[1]}'
    for actor in mission['units']:
        ax, ay = actor['pos']
        w, h = actor.get('footprint', (1, 1))
        if ax <= cell[0] < ax+w and ay <= cell[1] < ay+h:
            return f'map_actor:{mission_id}/{actor["id"]}'
    for obj in mission.get('objects', ()):
        if tuple(obj['pos']) == cell:
            return f'map_object:{mission_id}/{obj["id"]}'
    return f'map_tile:{mission_id}/{cell[0]},{cell[1]}'


def navigation_target(data, key):
    """Return (mission, anchor-cell or None), rejecting stale/invalid targets."""
    if key.startswith(('map_actor:', 'map_object:')):
        mid, cell, _, _ = map_resource_target(key, data)
        return mid, cell
    if key.startswith('editor_group:'):
        identifier = key.split(':', 1)[1]
        if '/' not in identifier:
            raise RuleError('Groupe invalide : ' + key)
        mid, gid = identifier.split('/', 1)
        snapshot = inspect_persistent_group(data, mid, gid)
        return mid, snapshot.cell or None
    if key.startswith('map_tile:'):
        identifier = key.split(':', 1)[1]
        if '/' not in identifier:
            raise RuleError('Case invalide : ' + key)
        mid, coords = identifier.split('/', 1)
        try:
            x, y = (int(v) for v in coords.split(','))
        except ValueError as exc:
            raise RuleError('Case invalide : ' + key) from exc
        mission = next((m for m in data['missions'] if m['id'] == mid), None)
        if mission is None or not (0 <= x < mission['board']['width']
                                   and 0 <= y < mission['board']['height']):
            raise RuleError('Case supprimée ou hors carte : ' + key)
        return mid, (x, y)
    if key.startswith('mission:'):
        mid = key.split(':', 1)[1]
        if not any(m['id'] == mid for m in data['missions']):
            raise RuleError('Mission supprimée : ' + key)
        return mid, None
    # Other indexed resources have no map projection; they are allowed
    # in history and resolved by the existing Workspace/Studio index.
    return None, None


class NavigationHistory:
    """Bounded, deduplicated back/forward stack; not Content undo/redo."""
    def __init__(self, limit=64):
        if type(limit) is not int or limit < 2:
            raise ValueError('Navigation history needs at least two entries')
        self.limit = limit
        self._entries = []
        self._cursor = -1

    @property
    def current(self):
        return self._entries[self._cursor] if self._cursor >= 0 else ''

    @property
    def can_back(self):
        return self._cursor > 0

    @property
    def can_forward(self):
        return self._cursor < len(self._entries) - 1

    def record(self, key):
        if not isinstance(key, str) or not key or ':' not in key:
            raise RuleError('Ressource de navigation invalide')
        if key == self.current:
            return False
        del self._entries[self._cursor + 1:]
        self._entries.append(key)
        if len(self._entries) > self.limit:
            self._entries.pop(0)
        self._cursor = len(self._entries) - 1
        return True

    def reset(self):
        self._entries.clear()
        self._cursor = -1

    def traverse(self, direction, is_valid):
        """Skip deleted entries. No cursor movement when no valid target."""
        if direction not in (-1, 1):
            raise ValueError('Navigation direction must be -1 or 1')
        i = self._cursor + direction
        while 0 <= i < len(self._entries):
            target = self._entries[i]
            if is_valid(target):
                self._cursor = i
                return target
            i += direction
        return ''
