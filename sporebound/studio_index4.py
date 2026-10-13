"""Unified, read-only resource references for Game Studio 4.0.

Projection of the existing Content and GameProject, not an extra manifest.
"""
from dataclasses import dataclass
import json
from unicodedata import normalize

from .workspace import ProjectWorkspaceIndex
from .model import Content
from .tactical_rpg3 import authored_rules_for_document


@dataclass(frozen=True, order=True)
class Reference:
    source: str
    target: str
    label: str


def fold(text):
    return ''.join(c for c in normalize('NFKD', str(text)).casefold()
                   if not 0x300 <= ord(c) <= 0x36f)


class StudioIndex:
    def __init__(self, content, project):
        self.content, self.project = content, project
        self.workspace = ProjectWorkspaceIndex(content, project)
        self.sections = self.workspace.sections()
        self.nodes = {n.key: n for items in self.sections.values() for n in items}
        self.references = self._references()
        # Read-only indexes are built once per model, not on every selection.
        self._search_text = {
            key: fold(' '.join((node.key, node.label, node.summary)))
            for key, node in self.nodes.items()
        }
        outgoing, incoming = {}, {}
        for link in self.references:
            outgoing.setdefault(link.source, []).append(link)
            incoming.setdefault(link.target, []).append(link)
        self._outgoing = {key: tuple(links) for key, links in outgoing.items()}
        self._incoming = {key: tuple(links) for key, links in incoming.items()}

    def _references(self):
        links = set()

        def add(source, target, label):
            if source in self.nodes and target in self.nodes:
                links.add(Reference(source, target, label))

        for c in self.project.campaigns:
            add('campaign:' + c['id'], 'mission:' + c['start_mission'], 'Départ')
        for m in self.content.missions.values():
            for mid in m.next_missions:
                add('mission:' + m.id, 'mission:' + mid, 'Mission suivante')
        for s in self.project.sieges:
            source = 'siege:' + s['id']
            add(source, 'campaign:' + s['campaign_id'], 'Campagne')
            for front, mid in s['fronts'].items():
                add(source, 'mission:' + mid, 'Front ' + front)
            for event in s.get('event_graph', []):
                key = 'strategic_event:' + s['id'] + '/' + event['id']
                add(source, key, 'Événement stratégique')

                def visit(expr):
                    kind, value = next(iter(expr.items()))
                    if kind in ('all', 'any'):
                        for child in value:
                            visit(child)
                    elif kind == 'not':
                        visit(value)
                    elif kind == 'fired':
                        add(key, 'strategic_event:' + s['id'] + '/' + value,
                            'Dépend de')
                    elif kind in ('battle_event', 'front_status', 'timeline_event'):
                        add(key, 'mission:' + s['fronts'][value['front']],
                            'Preuve ' + kind)

                visit(event['when'])
                for effect in event['effects']:
                    if effect.get('front') in s['fronts']:
                        add(key, 'mission:' + s['fronts'][effect['front']],
                            'Effet ' + effect['kind'])
        for mission in self.content.missions.values():
            source = 'mission:' + mission.id
            for actor in mission.units:
                key = 'map_actor:' + mission.id + '/' + actor.id
                add(source, key, 'Acteur placé')
                if actor.archetype:
                    add(key, 'actor:' + actor.archetype, 'Archétype')
            for obj in mission.objects:
                key = 'map_object:' + mission.id + '/' + obj['id']
                add(source, key, 'Objet placé')
                if obj.get('kind') in ('switch', 'ram', 'catapult') and obj.get('link'):
                    add(key, 'map_object:' + mission.id + '/' + obj['link'],
                        'Porte associée')
        story = self.project.story
        for reference, scene_id in story.get('after_strategic_event', {}).items():
            add('strategic_event:' + reference,
                'scene:' + scene_id, 'Scène après événement authentifié')
        for cid, sid in story.get('entry_scenes', {}).items():
            add('campaign:' + cid, 'scene:' + sid, 'Introduction')
        for mid, sid in story.get('after_mission', {}).items():
            add('mission:' + mid, 'scene:' + sid, 'Après victoire')
        for scene in story.get('scenes', []):
            for choice in scene['choices']:
                if 'next_scene' in choice:
                    add('scene:' + scene['id'], 'scene:' + choice['next_scene'],
                        'Choix ' + choice['id'])
        bindings = self.project.asset_registry().to_dict()['bindings'].get('sound', {})
        for clip in self.project.cinematics:
            kind = clip['trigger']['kind']
            source = (('campaign:' if kind == 'campaign_start'
                       else 'scene:' if kind == 'scene' else 'mission:')
                      + clip['trigger']['target'])
            add(source, 'cinematic:' + clip['id'], 'Déclenchement cinématique')
            for event in clip['events']:
                if event['kind'] == 'sound':
                    add('cinematic:' + clip['id'],
                        'asset:' + bindings.get(event['cue'], event['cue']),
                        'Piste audio')
        for asset in self.project.asset_registry().to_dict()['entries']:
            if asset['kind'] == 'animation':
                for frame in asset['frames']:
                    add('asset:' + asset['id'], 'asset:' + frame['sprite'], 'Sprite')
        return tuple(sorted(links))

    def search(self, query):
        terms = [fold(s) for s in query.split()]
        return tuple(node for key, node in sorted(self.nodes.items())
                     if all(term in self._search_text[key] for term in terms))

    def outgoing(self, key):
        return self._outgoing.get(key, ())

    def incoming(self, key):
        return self._incoming.get(key, ())

    def diagnostics(self, root, *, map_warnings=False):
        issues = [('error', 'asset:' + i['asset_id'], i['message'])
                  for i in self.workspace.asset_issues(root)]
        incoming = {r.target for r in self.references}
        for scene in self.project.story.get('scenes', []):
            key = 'scene:' + scene['id']
            if key not in incoming:
                issues.append(('warning', key, 'Scène sans point d’entrée connu'))
        for clip in self.project.cinematics:
            if not clip['events']:
                issues.append(('warning', 'cinematic:' + clip['id'],
                               'Cinématique vide'))
        if map_warnings:
            from .workspace_shell import map_reference_problems
            issues.extend(map_reference_problems(self.content))
        return tuple(sorted(issues))


class WorkspaceModelCache:
    """One validated StudioIndex reused for unchanged authored *values*.

    Editing may modify nested Content/Project dictionaries in place, so neither
    Python object identity nor a document revision alone is a valid key.
    Compare canonical JSON snapshots before rebuilding; a single old model is
    retained, never an unbounded cache of project generations.
    """

    def __init__(self):
        self._stamp = None
        self._model = None
        self.builds = 0

    def invalidate(self):
        self._stamp = None
        self._model = None

    def get(self, content_data, project):
        if project is None:
            raise ValueError("Workspace requires a game project")
        stamp = (json.dumps(content_data, sort_keys=True, ensure_ascii=True),
                 json.dumps(project.to_dict(), sort_keys=True, ensure_ascii=True))
        if self._model is not None and stamp == self._stamp:
            return self._model
        # Validate before changing the cache: failed edits cannot poison it.
        content = Content.from_dict(
            content_data, rules=authored_rules_for_document(content_data))
        model = StudioIndex(content, project)
        self._stamp, self._model = stamp, model
        self.builds += 1
        return model
