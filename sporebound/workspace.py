"""Read-only project inventory and validated Studio actions (no UI dependencies).

A workspace is a projection of Content and GameProject; it is NOT a third
manifest and never owns a second copy of either document's editable state.
"""
from copy import deepcopy
from dataclasses import dataclass

from .authoring import add_blank_mission
from .game_project import GameProject
from .model import Content, RuleError, require


GROUPS = (
    ('game', 'Jeu et menus'),
    ('campaign', 'Campagnes'),
    ('mission', 'Cartes et missions'),
    ('scene', 'Scénarios et dialogues'),
    ('actor', 'Personnages et monstres'),
    ('skill', 'Compétences'),
    ('job', 'Classes'),
    ('equipment', 'Équipements'),
    ('asset', 'Assets et animations'),
)


@dataclass(frozen=True)
class WorkspaceNode:
    kind: str
    id: str
    label: str
    summary: str

    @property
    def key(self):
        return f'{self.kind}:{self.id}'


class ProjectWorkspaceIndex:
    """Build a deterministic index directly from the currently edited documents."""

    def __init__(self, content, project):
        require(isinstance(content, Content), 'Workspace needs validated content')
        require(isinstance(project, GameProject), 'Workspace needs a game project')
        content.validate()
        project.validate(content)
        self.content = content
        self.project = project

    def sections(self):
        result = {kind: [] for kind, _ in GROUPS}
        result['game'].append(WorkspaceNode(
            'game', 'settings', self.project.title,
            f'{self.project.subtitle}\nLangue : {self.project.options["language"]}'
            f' | Emplacements : {self.project.save_slots}'))
        for campaign in self.project.campaigns:
            result['campaign'].append(WorkspaceNode(
                'campaign', campaign['id'], campaign['name'],
                f'Départ : {campaign["start_mission"]}\n{campaign["description"]}'))
        for mission in self.content.missions.values():
            result['mission'].append(WorkspaceNode(
                'mission', mission.id, mission.name,
                f'{mission.board.width} × {mission.board.height} | '
                f'{len(mission.units)} unités | {len(mission.objects)} objets'
                f'\nObjectif : {mission.objective} | '
                f'Suites : {", ".join(mission.next_missions) or "aucune"}'))
        for scene in self.project.story.get('scenes', []):
            result['scene'].append(WorkspaceNode(
                'scene', scene['id'], scene['title'],
                f'{scene.get("speaker", "")}\n'
                f'{len(scene.get("choices", []))} choix'))
        for aid, actor in self.content.archetypes.items():
            result['actor'].append(WorkspaceNode(
                'actor', aid, aid, f'Type : {actor.get("kind", "character")}'))
        for skill in self.content.skills.values():
            result['skill'].append(WorkspaceNode(
                'skill', skill.id, skill.name,
                f'Portée : {skill.range} | Cible : {skill.target}'))
        for jid in self.content.jobs:
            result['job'].append(WorkspaceNode('job', jid, jid, 'Classe jouable'))
        for eid in self.content.equipment:
            result['equipment'].append(WorkspaceNode('equipment', eid, eid, 'Équipement'))
        for asset in self.project.asset_registry().to_dict()['entries']:
            result['asset'].append(WorkspaceNode(
                'asset', asset['id'], asset['id'],
                f'{asset["kind"]} : {asset.get("path", str(len(asset.get("frames", []))) + " images")}'))
        return {kind: tuple(sorted(result[kind], key=lambda n: n.id.casefold()))
                for kind, _ in GROUPS}

    def node(self, key):
        for nodes in self.sections().values():
            for node in nodes:
                if node.key == key:
                    return node
        raise RuleError(f'Workspace item no longer exists: {key}')

    def asset_issues(self, project_directory):
        return self.project.asset_registry().diagnostics(project_directory)


def create_blank_mission(content_data, project, mission_id, name, width, height):
    """Return a new validated content dict; never mutate project or input on failure."""
    require(isinstance(project, GameProject), 'Missing game project')
    updated = add_blank_mission(content_data, mission_id, name, width, height)
    project.validate(Content.from_dict(updated))
    return updated


def duplicate_mission(content_data, project, source_id, new_id, new_name):
    """Copy a level as an independent mission without inheriting outgoing links."""
    require(isinstance(new_id, str) and bool(new_id.strip()) and len(new_id) <= 64,
            'Mission id needs 1..64 characters')
    require(isinstance(new_name, str) and bool(new_name.strip()),
            'Mission name must not be empty')
    updated = deepcopy(content_data)
    require(new_id not in {m['id'] for m in updated['missions']},
            f'Mission already exists: {new_id}')
    source = next((m for m in updated['missions'] if m['id'] == source_id), None)
    require(source is not None, f'Unknown mission: {source_id}')
    copied = deepcopy(source)
    copied.update(id=new_id, name=new_name, next_missions=[])
    updated['missions'].append(copied)
    project.validate(Content.from_dict(updated))
    return updated


def create_campaign(project, content, campaign_id, name, start_mission):
    """Create and validate an independent campaign in the existing manifest."""
    data = deepcopy(project.to_dict())
    data['campaigns'].append({
        'id': campaign_id, 'name': name, 'description': '',
        'start_mission': start_mission,
    })
    return GameProject.from_dict(data, content)
