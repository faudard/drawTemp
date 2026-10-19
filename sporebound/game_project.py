"""High-level game presentation and campaign authoring; independent of Tk and Battle.

The project manifest is intentionally separate from the validated tactical
content v1, so editing a title screen cannot rewrite combat/replay contracts.
"""
from dataclasses import dataclass, field
from copy import deepcopy
import json
from pathlib import Path

from .campaign import Campaign
from .model import RuleError, require
from .storage import write_json


@dataclass
class GameProject:
    title: str = 'DrawTemp — RPG tactique'
    subtitle: str = 'Une aventure tactique'
    campaigns: list[dict] = field(default_factory=list)
    options: dict = field(default_factory=lambda: {
        'language': 'fr', 'music_volume': 70, 'effects_volume': 70,
        'fullscreen': False,
    })
    save_slots: int = 3
    story: dict = field(default_factory=dict)
    version: int = 1
    assets: dict = field(default_factory=dict)
    sieges: list[dict] = field(default_factory=list)
    cinematics: list[dict] = field(default_factory=list)
    exploration: dict = field(default_factory=dict)
    battle_support: list[dict] = field(default_factory=list)
    world: dict = field(default_factory=dict)
    campaign_flow: dict = field(default_factory=dict)
    extensions: dict = field(default_factory=dict)
    # Optional R25 profile manifest; omission preserves legacy v1 JSON and digests.
    game_modes: dict = field(default_factory=dict)
    # Opt-in R25.B scene graph; absent in historical manifests.
    scene_routes: dict = field(default_factory=dict)

    @classmethod
    def default(cls, content):
        first = next(iter(content.missions))
        return cls(campaigns=[{'id': 'main', 'name': 'Campagne principale',
                               'start_mission': first, 'description': ''}])

    @classmethod
    def from_dict(cls, data, content):
        require(isinstance(data, dict), 'Project must be an object')
        try:
            project = cls(**deepcopy(data))
        except (TypeError, ValueError) as exc:
            raise RuleError(f'Invalid project structure: {exc}') from exc
        project.validate(content)
        return project

    @classmethod
    def load(cls, path, content):
        return cls.from_dict(json.loads(Path(path).read_text(encoding='utf-8')), content)

    def to_dict(self):
        return {'version': self.version, 'title': self.title, 'subtitle': self.subtitle,
                'campaigns': deepcopy(self.campaigns), 'options': deepcopy(self.options),
                'save_slots': self.save_slots,
                **({'story': deepcopy(self.story)} if self.story else {}),
                **({'assets': deepcopy(self.assets)} if self.assets else {}),
                **({'sieges': deepcopy(self.sieges)} if self.sieges else {}),
                **({'cinematics': deepcopy(self.cinematics)} if self.cinematics else {}),
                **({'exploration': deepcopy(self.exploration)} if self.exploration else {}),
                **({'world': deepcopy(self.world)} if self.world else {}),
                **({'battle_support': deepcopy(self.battle_support)} if self.battle_support else {}),
                **({'campaign_flow': deepcopy(self.campaign_flow)} if self.campaign_flow else {}),
                **({'extensions': deepcopy(self.extensions)} if self.extensions else {}),
                **({'game_modes': deepcopy(self.game_modes)} if self.game_modes else {}),
                **({'scene_routes': deepcopy(self.scene_routes)} if self.scene_routes else {})}

    def asset_registry(self):
        from .assets import AssetRegistry
        require(isinstance(self.assets, dict), 'Project assets must be an object')
        return AssetRegistry(self.assets if self.assets else None)

    def validate(self, content):
        self.asset_registry()
        require(type(self.version) is int and self.version == 1, 'Unsupported game project version')
        require(isinstance(self.title, str) and 0 < len(self.title.strip()) <= 120,
                'Title must contain 1..120 characters')
        require(isinstance(self.subtitle, str) and len(self.subtitle) <= 240,
                'Subtitle must contain at most 240 characters')
        require(type(self.save_slots) is int and 1 <= self.save_slots <= 9,
                'Save slots must be between 1 and 9')
        require(isinstance(self.options, dict), 'Options must be an object')
        require(set(self.options) == {'language', 'music_volume', 'effects_volume', 'fullscreen'},
                'Unknown or missing option')
        require(self.options['language'] in ('fr', 'en'), 'Language must be fr or en')
        require(type(self.options['fullscreen']) is bool, 'Fullscreen must be boolean')
        for key in ('music_volume', 'effects_volume'):
            volume = self.options[key]
            require(type(volume) is int and 0 <= volume <= 100, f'{key}: expected 0..100')
        require(isinstance(self.campaigns, list) and bool(self.campaigns),
                'At least one campaign required')
        ids = set()
        for campaign in self.campaigns:
            require(isinstance(campaign, dict) and
                    set(campaign) == {'id', 'name', 'description', 'start_mission'},
                    'Campaign needs id, name, description, start_mission')
            cid = campaign['id']
            require(isinstance(cid, str) and 0 < len(cid) <= 64 and
                    all(c.isalnum() or c in '-_' for c in cid) and cid not in ids,
                    'Invalid or duplicate campaign id')
            ids.add(cid)
            require(isinstance(campaign['name'], str) and 0 < len(campaign['name'].strip()) <= 120,
                    'Campaign needs a name')
            require(isinstance(campaign['description'], str) and len(campaign['description']) <= 1000,
                    'Campaign description too long')
            require(campaign['start_mission'] in content.missions,
                    f'Unknown starting mission: {campaign["start_mission"]}')
        from .project_extensions import validate_project_extensions
        validate_project_extensions(self.extensions, content=content, campaigns=self.campaigns)
        # R32: reject malformed geometry on load, even outside the Studio.
        from .physics_scenes import EXTENSION as PHYSICS_EXTENSION, physics_scene_ids, validate_physics_catalog
        if PHYSICS_EXTENSION in self.extensions:
            validate_physics_catalog(self.extensions[PHYSICS_EXTENSION]["data"],
                                     known_ids=physics_scene_ids(content, self))
        if "drawtemp.metroidvania" in self.extensions:
            from .metroidvania import validate_metroidvania
            validate_metroidvania(
                self.extensions["drawtemp.metroidvania"]["data"],
                scene_ids=self.exploration,
            )
        from .living_world import EXTENSION, validate_living_world
        if EXTENSION in self.extensions:
            validate_living_world(
                self.extensions[EXTENSION]["data"],
                set(self.exploration) | set(content.missions))
        from .campaign_flow import validate_flow
        validate_flow(self.campaign_flow, content)
        from .siege_authoring import validate_all
        validate_all(self.sieges, content, self.campaigns)
        from .cinematics import validate_cinematics
        validate_cinematics(self.cinematics, content, self.campaigns,
                            self.story.get("scenes", []))
        from .narrative import validate_story
        validate_story(self.story, content, self.campaigns)
        # Only a verified node in the authored siege may trigger a narrative scene.
        strategic_refs = {
            siege['id'] + '/' + node['id']
            for siege in self.sieges
            for node in siege.get('event_graph', [])
        }
        for reference in self.story.get('after_strategic_event', {}):
            require(reference in strategic_refs,
                    'Unknown strategic narrative trigger: ' + reference)
        from .exploration import validate_exploration
        validate_exploration(self.exploration, self.story)
        from .world_map import validate_world
        validate_world(self.world, content, self.campaigns, self.story)
        from .game_modes import validate_game_modes
        validate_game_modes(self.game_modes, content, self)
        from .scene_router import validate_scene_routes
        validate_scene_routes(self.scene_routes, content, self)
        require(isinstance(self.battle_support, list) and len(self.battle_support) <= 40,
                'Invalid battle support rules')
        for spec in self.battle_support:
            require(isinstance(spec, dict) and set(spec) ==
                    {'mission', 'flag', 'gte', 'potion_bonus'},
                    'Invalid battle support rule')
            require(spec['mission'] in content.missions, 'Unknown support mission')
            require(isinstance(spec['flag'], str) and 0 < len(spec['flag']) <= 64
                    and all(ch.isalnum() or ch == '_' for ch in spec['flag']),
                    'Invalid support flag')
            require(type(spec['gte']) is int and 1 <= spec['gte'] <= 1000,
                    'Invalid support threshold')
            require(type(spec['potion_bonus']) is int and
                    1 <= spec['potion_bonus'] <= 6, 'Invalid support bonus')

    def save(self, path, content):
        self.validate(content)
        write_json(path, self.to_dict())

    def campaign(self, campaign_id):
        return next((c for c in self.campaigns if c['id'] == campaign_id), None)

    def new_game(self, campaign_id, content):
        self.validate(content)
        campaign = self.campaign(campaign_id)
        require(campaign is not None, 'Unknown campaign')
        from .campaign_flow import definition_digest
        progress = Campaign(unlocked=[campaign['start_mission']],
                            flow_digest=definition_digest(self.campaign_flow))
        from .narrative import StoryBook
        StoryBook(self.story, content, self.campaigns).initialize(progress, campaign_id)
        return progress


def _slot_path(project_path, project, campaign_id, slot):
    require(project.campaign(campaign_id) is not None, 'Unknown campaign')
    require(type(slot) is int and 1 <= slot <= project.save_slots, 'Invalid save slot')
    path = Path(project_path)
    return path.with_name(path.stem + '_saves') / campaign_id / f'slot_{slot}.json'


def save_slot(project_path, project, content, campaign_id, slot, progress):
    """Atomic save using the existing Campaign format and strict slot paths."""
    project.validate(content)
    require(isinstance(progress, Campaign), 'No active campaign to save')
    require(set(progress.unlocked + progress.completed) <= set(content.missions),
            'Campaign references a mission that no longer exists')
    path = _slot_path(project_path, project, campaign_id, slot)
    from .narrative import StoryBook
    from .campaign_flow import verify_save
    verify_save(progress, project.campaign_flow)
    StoryBook(project.story, content, project.campaigns).initialize(progress, campaign_id)
    progress.save(path)
    return path


def load_slot(project_path, project, content, campaign_id, slot):
    project.validate(content)
    path = _slot_path(project_path, project, campaign_id, slot)
    progress = Campaign.load(path)
    from .campaign_flow import verify_save
    verify_save(progress, project.campaign_flow)
    from .narrative import StoryBook
    StoryBook(project.story, content, project.campaigns).initialize(progress, campaign_id)
    require(set(progress.unlocked + progress.completed) <= set(content.missions),
            'Save references a mission that no longer exists')
    return progress
