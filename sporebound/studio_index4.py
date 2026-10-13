"""Unified, read-only resource references for Game Studio 4.0.

Projection of the existing Content and GameProject, not an extra manifest.
"""
from dataclasses import dataclass
from unicodedata import normalize

from .workspace import ProjectWorkspaceIndex


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
            for obj in mission.objects:
                if obj.get('kind') in ('switch', 'ram', 'catapult') and obj.get('link'):
                    add('map_object:' + mission.id + '/' + obj['id'],
                        'map_object:' + mission.id + '/' + obj['link'],
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
        return tuple(node for _, node in sorted(self.nodes.items())
                     if all(term in fold(' '.join((node.key, node.label, node.summary)))
                            for term in terms))

    def outgoing(self, key):
        return tuple(link for link in self.references if link.source == key)

    def incoming(self, key):
        return tuple(link for link in self.references if link.target == key)

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
