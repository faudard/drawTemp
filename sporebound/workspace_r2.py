"""R2 — headless Workspace UX helpers using existing StudioIndex/Content.

No additional project manifest and no Tk imports. UI preferences remain
separate from the authored game data.
"""
from dataclasses import dataclass

from .model import RuleError
from .workspace_editing import EditableField, WorkspacePropertyCommand, editable_form, _parse


MIXED = '(mixte)'


@dataclass(frozen=True)
class BatchForm:
    keys: tuple
    baselines: tuple
    mission_id: str
    fields: tuple
    mixed: tuple


def batch_form(data, keys):
    """Intersection of typed properties, preserving each resource fingerprint."""
    keys = tuple(keys)
    if len(keys) < 2 or len(keys) != len(set(keys)):
        raise RuleError('Sélectionner au moins deux ressources distinctes')
    forms = tuple(editable_form(data, key) for key in keys)
    if (len({key.split(':', 1)[0] for key in keys}) != 1 or
            len({form.mission_id for form in forms}) != 1):
        raise RuleError('Sélection multiple : même type et même mission requis')
    fields, mixed = [], []
    for first in forms[0].fields:
        others = []
        for form in forms[1:]:
            match = next((f for f in form.fields if
                          f.name == first.name and f.kind == first.kind), None)
            if match is None:
                break
            others.append(match)
        else:
            choices = tuple(value for value in first.choices if
                            all(value in field.choices for field in others))
            if first.kind == 'choice' and not choices:
                continue
            if any(other.value != first.value for other in others):
                mixed.append(first.name)
            fields.append(EditableField(
                first.name, first.label, first.value, first.kind, choices))
    if not fields:
        raise RuleError('Aucune propriété commune éditable')
    return BatchForm(keys, tuple(form.baseline for form in forms),
                     forms[0].mission_id, tuple(fields), tuple(mixed))


@dataclass(frozen=True)
class BatchPropertyCommand:
    """A single EditingContext preview/commit; no partial mutations or stale edits."""
    keys: tuple
    baselines: tuple
    values: tuple
    kind: str = 'workspace-batch-property'
    views: tuple = ('renderer', 'minimap', 'inspector', 'workspace')

    def transform(self, data, mission_id):
        batch = batch_form(data, self.keys)
        if batch.mission_id != mission_id or batch.baselines != self.baselines:
            raise RuleError('Sélection périmée : réouvrir l’inspecteur')
        allowed = {field.name: field for field in batch.fields}
        raw = dict(self.values)
        if not raw or len(raw) != len(self.values) or not raw.keys() <= allowed.keys():
            raise RuleError('Champs de sélection multiple non autorisés')
        parsed = {key: _parse(allowed[key], value) for key, value in raw.items()}
        result = data
        changed = False
        for key, baseline in zip(batch.keys, batch.baselines):
            fields = {field.name: field.value for field in editable_form(result, key).fields}
            edits = tuple((name, value) for name, value in parsed.items()
                          if value != fields[name])
            if edits:
                result = WorkspacePropertyCommand(key, baseline, edits).transform(
                    result, mission_id)
                changed = True
        if not changed:
            raise RuleError('Aucune propriété modifiée')
        return result


@dataclass(frozen=True)
class ResourceImpact:
    key: str
    incoming: tuple
    outgoing: tuple

    @property
    def has_dependents(self):
        # A mission contains its placed resources, but this ownership does
        # not by itself imply that a third-party reference must be rewritten.
        return bool(tuple(ref for ref in self.incoming
                          if not (ref.source.startswith('mission:') and
                                  ref.label in ('Acteur placé', 'Objet placé',
                                                'Groupe d’édition'))))

    def require_safe_delete(self):
        if self.has_dependents:
            sources = ', '.join(sorted({ref.source for ref in self.incoming
                                        if not ref.source.startswith('mission:')}))
            raise RuleError('Suppression bloquée : références entrantes : ' + sources)


def dependency_impact(index, key):
    """Only StudioIndex owns the graph; never invent a second graph of links."""
    if key not in index.nodes:
        raise RuleError('Ressource disparue : ' + key)
    return ResourceImpact(key, tuple(index.incoming(key)), tuple(index.outgoing(key)))


class ExplorerState:
    """Ephemeral UI choices keyed by canonical Workspace identifiers."""
    def __init__(self, *, limit=32):
        self.limit = limit
        self.favorites = set()
        self.recents = []

    def reconcile(self, index):
        known = set(index.nodes)
        self.favorites.intersection_update(known)
        self.recents = [key for key in self.recents if key in known][:self.limit]

    def toggle_favorite(self, key):
        if key in self.favorites:
            self.favorites.remove(key)
            return False
        self.favorites.add(key)
        return True

    def visit(self, key):
        self.recents = [key] + [item for item in self.recents if item != key]
        self.recents = self.recents[:self.limit]

    def shown(self, index, query='', *, kind='all', scope='all'):
        """Use the canonical search; filters never mutate the StudioIndex."""
        self.reconcile(index)
        if scope not in ('all', 'favorites', 'recents'):
            raise RuleError('Filtre Workspace inconnu : ' + scope)
        if kind != 'all' and kind not in index.sections:
            raise RuleError('Famille de ressources inconnue : ' + kind)
        visible = {node.key for node in index.search(query)}
        if kind != 'all':
            visible = {key for key in visible if key.startswith(kind + ':')}
        if scope == 'favorites':
            visible.intersection_update(self.favorites)
        elif scope == 'recents':
            visible.intersection_update(self.recents)
        return visible


def validate_drop(data, mission_id, key):
    """Validate tree origin before handing off to 3.7.31's palette placement."""
    from .workspace_shell import palette_source_for_tree
    return palette_source_for_tree(key, data, mission_id)
