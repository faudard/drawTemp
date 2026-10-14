"""3.7.31 — Shared, Tk-free workspace inspection and actionable map problems.

The Workspace, map inspector and problems panel project the current Content;
nothing here writes gameplay documents or creates a competing resource registry.
"""
from dataclasses import dataclass
import json
from pathlib import Path

from .model import RuleError
from .workspace import GROUPS


@dataclass(frozen=True)
class ContextSnapshot:
    kind: str
    title: str
    detail: str
    mission_id: str = ''
    cell: tuple = ()
    entity_id: str = ''


def inspect_resource(node):
    return ContextSnapshot(node.kind, node.label, node.summary)


def inspect_map(data, mission_id, cell, cells=(), *, preferred_kind='', preferred_id=''):
    """One inspector projection for tiles, actors, objects and selected groups."""
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    if mission is None:
        raise RuleError('Mission introuvable : ' + mission_id)
    cell = tuple(cell)
    width, height = mission['board']['width'], mission['board']['height']
    if len(cell) != 2 or not all(type(n) is int for n in cell) or not (
            0 <= cell[0] < width and 0 <= cell[1] < height):
        raise RuleError('Case hors de la carte.')
    selected = tuple(sorted({tuple(p) for p in cells}))
    if len(selected) > 1:
        return ContextSnapshot('group', 'GROUPE — sélection de cases',
                               f'{len(selected)} cases | Mission : {mission["name"]}\n'
                               f'Ancre : {cell}\n'
                               'Déplacer/copier via les outils de sélection existants.',
                               mission_id, cell)
    actor = next((a for a in mission['units']
                  if tuple(a['pos']) == cell and
                  (not preferred_id or
                   preferred_kind == 'actor' and a['id'] == preferred_id)), None)
    obj = next((o for o in mission.get('objects', [])
                if tuple(o['pos']) == cell and
                (not preferred_id or
                 preferred_kind == 'object' and o['id'] == preferred_id)), None)
    if preferred_id and not (actor or obj):
        raise RuleError('Ressource déplacée ou supprimée : ' + preferred_id)
    tile = next((t for t in mission['board'].get('tiles', [])
                 if tuple(t['pos']) == cell), {})
    terrain = ('Sol : ' + str(tile.get('surface', 'grass')) +
               ' | Décor : ' + str(tile.get('feature', '') or 'aucun') +
               ' | Hauteur : ' + str(tile.get('height', 0)))
    if actor:
        return ContextSnapshot(
            'actor', 'ACTEUR — ' + actor.get('name', actor['id']),
            f'ID : {actor["id"]} | Camp : {actor["team"]} | Position : {cell}\n'
            f'Archétype : {actor.get("archetype", "libre") or "libre"}\n'
            f'PV : {actor.get("hp", "hérités")} | {terrain}',
            mission_id, cell, actor['id'])
    if obj:
        return ContextSnapshot(
            'object', 'OBJET — ' + obj['id'],
            f'Type : {obj["kind"]} | Position : {cell}\n'
            f'Référence : {obj.get("link", "") or "aucune"}\n{terrain}',
            mission_id, cell, obj['id'])
    return ContextSnapshot('cell', 'CASE — ' + str(cell),
                           'Mission : ' + mission['name'] + '\n' + terrain,
                           mission_id, cell)


def inspect_persistent_group(data, mission_id, group_id):
    """Project the canonical 3.7.25 editor hierarchy, including descendants.

    Group ownership remains in Mission.editor_groups and the existing map
    Treeview: this creates no parallel group schema or mutable cache.
    """
    from .editor_groups import descendant_groups, group_display_cells
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    if mission is None:
        raise RuleError('Mission introuvable : ' + mission_id)
    groups = descendant_groups(mission, group_id)
    root = next(g for g in groups if g['id'] == group_id)
    cells = sorted(group_display_cells(mission, group_id))
    counts = {field: sum(len(g[field]) for g in groups)
              for field in ('cells', 'unit_ids', 'object_ids', 'structure_ids')}
    detail = (f'ID : {group_id} | Mission : {mission["name"]}\n'
              f'Parent : {root["parent"] or "racine"} | '
              f'Sous-groupes : {len(groups)-1}\n'
              f'Cases libres : {counts["cells"]} | '
              f'Acteurs : {counts["unit_ids"]} | '
              f'Objets : {counts["object_ids"]} | '
              f'Structures : {counts["structure_ids"]}\n'
              f'Emprise totale : {len(cells)} cases')
    return ContextSnapshot('editor_group', 'GROUPE — ' + root['name'],
                           detail, mission_id, cells[0] if cells else (),
                           group_id)


def map_reference_problems(content):
    """Authoring warnings with stable, navigable keys, not schema errors.

    A door with no incoming link is valid to play, but often signals an
    unfinished lever/ram association. Resolve by linking an interactive
    object from the existing palette. No invalid Content is ever stored.
    """
    issues = []
    for mission in content.missions.values():
        linked = {o.get('link') for o in mission.objects
                  if o.get('kind') in ('switch', 'ram', 'catapult')}
        for obj in mission.objects:
            if obj['kind'] == 'door' and obj['id'] not in linked:
                issues.append((
                    'warning', f'map_object:{mission.id}/{obj["id"]}',
                    'Porte sans référence entrante (levier, bélier ou catapulte).'))
    return tuple(sorted(issues))


def problem_delta(before, after):
    """Return added/resolved triples without reloading the entire Studio."""
    previous, current = set(before), set(after)
    return tuple(sorted(current - previous)), tuple(sorted(previous - current))


def map_resource_target(key, data):
    """Resolve a live Workspace key to a real map position, never stale coords."""
    if not key.startswith(('map_actor:', 'map_object:')):
        return None
    kind, identifier = key.split(':', 1)
    if '/' not in identifier:
        raise RuleError('Identifiant de carte invalide : ' + key)
    mid, eid = identifier.split('/', 1)
    mission = next((m for m in data['missions'] if m['id'] == mid), None)
    if mission is None:
        raise RuleError('Mission introuvable : ' + mid)
    entries = mission['units'] if kind == 'map_actor' else mission.get('objects', [])
    record = next((o for o in entries if o['id'] == eid), None)
    if record is None:
        raise RuleError('Élément supprimé : ' + key)
    return mid, tuple(record['pos']), ('unit' if kind == 'map_actor' else 'object'), eid


def palette_source_for_tree(key, data, mission_id):
    """Resolve a drag originating in Workspace into the existing palette."""
    from .entity_palette import entity_entries
    if key.startswith('actor:'):
        source = 'archetype:' + key.split(':', 1)[1]
    elif key.startswith('map_actor:'):
        mid, entity_id = key.partition(':')[2].split('/', 1)
        if mid != mission_id:
            raise RuleError('Changer de mission avant de dupliquer cet acteur.')
        source = 'actor:' + entity_id
    elif key.startswith('map_object:'):
        mid, entity_id = key.partition(':')[2].split('/', 1)
        if mid != mission_id:
            raise RuleError('Changer de mission avant de copier cet objet.')
        mission = next(m for m in data['missions'] if m['id'] == mid)
        original = next((o for o in mission.get('objects', [])
                         if o['id'] == entity_id), None)
        if original is None:
            raise RuleError('Objet introuvable : ' + key)
        source = 'object:' + original['kind']
    else:
        raise RuleError('Déposer un acteur ou objet depuis le Workspace.')
    return next((entry for entry in entity_entries(data, mission_id)
                 if entry.id == source),
                None) or _missing_entry(key)


def _missing_entry(key):
    raise RuleError('Ressource de palette introuvable : ' + key)


class LayoutStore:
    """Atomic UI-only preferences; never part of Content or GameProject."""
    def __init__(self, path):
        self.path = Path(path)

    @staticmethod
    def clean(data):
        if not isinstance(data, dict):
            return {}
        safe = {}
        for key in ('outer_left', 'outer_right', 'vertical'):
            value = data.get(key)
            if type(value) is int and value >= 0:
                safe[key] = value
        tab = data.get('tab')
        if isinstance(tab, str) and len(tab) <= 100:
            safe['tab'] = tab
        for key in ('favorites', 'recents'):
            values = data.get(key)
            if isinstance(values, (list, tuple)):
                unique = []
                for value in values:
                    if (isinstance(value, str) and ':' in value and
                            len(value) <= 256 and value not in unique):
                        unique.append(value)
                    if len(unique) >= 64:
                        break
                safe[key] = unique
        if data.get('family_filter') in ('all',) + tuple(
                kind for kind, _ in GROUPS):
            safe['family_filter'] = data['family_filter']
        if data.get('scope_filter') in ('all', 'favorites', 'recents'):
            safe['scope_filter'] = data['scope_filter']
        return safe

    def load(self):
        try:
            return self.clean(json.loads(self.path.read_text(encoding='utf-8')))
        except (OSError, ValueError, TypeError):
            return {}

    def save(self, layout):
        cleaned = self.clean(layout)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + '.tmp')
        temporary.write_text(json.dumps(cleaned, sort_keys=True), encoding='utf-8')
        temporary.replace(self.path)
